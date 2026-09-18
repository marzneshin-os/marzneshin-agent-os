#!/usr/bin/env python3
"""Tests for watchdog.py — circuit breaker, backoff, and health-check logic.

Uses VirtualClock so time advances deterministically. Mocks subprocess and
urllib so no real services are contacted.

Run:  python3 -m unittest tests/test_watchdog.py -v
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

from lib import clock
from lib.clock import VirtualClock


def _make_temp_dirs():
    tmpdir = Path(tempfile.mkdtemp())
    config_dir = tmpdir / "configs"
    config_dir.mkdir()
    state_dir = tmpdir / "state"
    state_dir.mkdir()
    log_dir = state_dir / "logs"
    log_dir.mkdir()
    return tmpdir, config_dir, state_dir


def _write_config(config_dir, services):
    path = config_dir / "services.json"
    with open(path, "w") as f:
        json.dump(services, f)
    return path


MINIMAL_CONFIG = {
    "test_svc": {
        "command": "echo hello",
        "port": 9999,
        "health": {
            "type": "http",
            "path": "/",
            "expected_status": [200],
            "timeout_s": 1,
            "critical": True,
        },
    },
}

PROCESS_CONFIG = {
    "bg_worker": {
        "command": "my_worker --daemon",
        "health": {
            "type": "process",
        },
    },
}


class WatchdogTestBase(unittest.TestCase):

    def setUp(self):
        self.vclock = VirtualClock(seed=42)
        clock.set_clock(self.vclock)
        self.tmpdir, self.config_dir, self.state_dir = _make_temp_dirs()
        _write_config(self.config_dir, MINIMAL_CONFIG)
        import watchdog
        self._orig_config = watchdog.CONFIG_PATH
        self._orig_state = watchdog.STATE_PATH
        self._orig_log = watchdog.LOG_DIR
        self._orig_root = watchdog.PROJECT_ROOT
        watchdog.CONFIG_PATH = self.config_dir / "services.json"
        watchdog.STATE_PATH = self.state_dir / "watchdog.json"
        watchdog.LOG_DIR = self.state_dir / "logs"
        watchdog.PROJECT_ROOT = self.tmpdir

    def tearDown(self):
        import watchdog
        watchdog.CONFIG_PATH = self._orig_config
        watchdog.STATE_PATH = self._orig_state
        watchdog.LOG_DIR = self._orig_log
        watchdog.PROJECT_ROOT = self._orig_root
        clock.set_clock(None)

        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class TestCircuitBreakerTransitions(WatchdogTestBase):

    def test_starts_closed(self):
        import watchdog
        state = watchdog.load_state()
        svc_state = watchdog.ensure_service_state(state, "test_svc")
        self.assertEqual(svc_state["circuit"], "closed")
        self.assertEqual(svc_state["consecutive_failures"], 0)

    def test_stays_closed_below_threshold(self):
        import watchdog
        state = watchdog.load_state()
        svc_state = watchdog.ensure_service_state(state, "test_svc")
        for _ in range(watchdog.FAILURE_THRESHOLD - 1):
            watchdog.record_failure(svc_state)
        self.assertEqual(svc_state["circuit"], "closed")
        self.assertEqual(
            svc_state["consecutive_failures"],
            watchdog.FAILURE_THRESHOLD - 1,
        )

    def test_opens_at_threshold(self):
        import watchdog
        state = watchdog.load_state()
        svc_state = watchdog.ensure_service_state(state, "test_svc")
        for _ in range(watchdog.FAILURE_THRESHOLD):
            result = watchdog.record_failure(svc_state)
        self.assertEqual(result, "open")
        self.assertEqual(svc_state["circuit"], "open")
        self.assertIsNotNone(svc_state["backoff_until"])

    def test_open_to_half_open_after_cooldown(self):
        import watchdog
        state = watchdog.load_state()
        svc_state = watchdog.ensure_service_state(state, "test_svc")
        for _ in range(watchdog.FAILURE_THRESHOLD):
            watchdog.record_failure(svc_state)
        self.assertEqual(svc_state["circuit"], "open")

        self.vclock.advance(seconds=watchdog.INITIAL_COOLDOWN_S + 30)

        can_restart, reason = watchdog.should_attempt_restart(svc_state)
        self.assertTrue(can_restart)
        self.assertEqual(svc_state["circuit"], "half_open")
        self.assertIn("HALF_OPEN", reason)

    def test_open_blocked_during_cooldown(self):
        import watchdog
        state = watchdog.load_state()
        svc_state = watchdog.ensure_service_state(state, "test_svc")
        for _ in range(watchdog.FAILURE_THRESHOLD):
            watchdog.record_failure(svc_state)

        can_restart, reason = watchdog.should_attempt_restart(svc_state)
        self.assertFalse(can_restart)
        self.assertIn("cooldown", reason)

    def test_half_open_to_closed_on_success(self):
        import watchdog
        state = watchdog.load_state()
        svc_state = watchdog.ensure_service_state(state, "test_svc")
        for _ in range(watchdog.FAILURE_THRESHOLD):
            watchdog.record_failure(svc_state)
        self.vclock.advance(seconds=watchdog.INITIAL_COOLDOWN_S + 30)
        watchdog.should_attempt_restart(svc_state)
        self.assertEqual(svc_state["circuit"], "half_open")

        watchdog.record_success(svc_state)
        self.assertEqual(svc_state["circuit"], "closed")
        self.assertEqual(svc_state["consecutive_failures"], 0)

    def test_half_open_back_to_open_on_failure(self):
        import watchdog
        state = watchdog.load_state()
        svc_state = watchdog.ensure_service_state(state, "test_svc")
        for _ in range(watchdog.FAILURE_THRESHOLD):
            watchdog.record_failure(svc_state)
        self.vclock.advance(seconds=watchdog.INITIAL_COOLDOWN_S + 30)
        watchdog.should_attempt_restart(svc_state)
        self.assertEqual(svc_state["circuit"], "half_open")

        svc_state["consecutive_failures"] = watchdog.FAILURE_THRESHOLD - 1
        result = watchdog.record_failure(svc_state)
        self.assertEqual(result, "open")

    def test_reset_clears_circuit(self):
        import watchdog
        state = watchdog.load_state()
        svc_state = watchdog.ensure_service_state(state, "test_svc")
        for _ in range(watchdog.FAILURE_THRESHOLD):
            watchdog.record_failure(svc_state)
        self.assertEqual(svc_state["circuit"], "open")

        with patch.object(watchdog, "emit_health_event"):
            watchdog.reset_circuit(state, "test_svc", False)
        reloaded = watchdog.load_state()
        svc = reloaded["services"]["test_svc"]
        self.assertEqual(svc["circuit"], "closed")
        self.assertEqual(svc["consecutive_failures"], 0)


class TestExponentialBackoff(WatchdogTestBase):

    def test_initial_cooldown(self):
        import watchdog
        state = watchdog.load_state()
        svc_state = watchdog.ensure_service_state(state, "test_svc")
        self.assertEqual(
            svc_state["cooldown_seconds"],
            watchdog.INITIAL_COOLDOWN_S,
        )

    def test_cooldown_doubles_after_open(self):
        import watchdog
        state = watchdog.load_state()
        svc_state = watchdog.ensure_service_state(state, "test_svc")
        for _ in range(watchdog.FAILURE_THRESHOLD):
            watchdog.record_failure(svc_state)
        self.assertEqual(
            svc_state["cooldown_seconds"],
            watchdog.INITIAL_COOLDOWN_S * watchdog.BACKOFF_MULTIPLIER,
        )

    def test_cooldown_capped_at_max(self):
        import watchdog
        state = watchdog.load_state()
        svc_state = watchdog.ensure_service_state(state, "test_svc")
        svc_state["cooldown_seconds"] = watchdog.MAX_COOLDOWN_S
        for _ in range(watchdog.FAILURE_THRESHOLD):
            watchdog.record_failure(svc_state)
        self.assertLessEqual(svc_state["cooldown_seconds"], watchdog.MAX_COOLDOWN_S)

    def test_jitter_within_bounds(self):
        import watchdog
        base = 60
        results = set()
        for _ in range(100):
            jittered = watchdog.compute_jittered_cooldown(base)
            results.add(jittered)
            self.assertGreaterEqual(jittered, base * (1 - watchdog.JITTER_FACTOR))
            self.assertLessEqual(jittered, base * (1 + watchdog.JITTER_FACTOR))
        self.assertGreater(len(results), 1, "jitter must produce different values")

    def test_cooldown_resets_on_success(self):
        import watchdog
        state = watchdog.load_state()
        svc_state = watchdog.ensure_service_state(state, "test_svc")
        for _ in range(watchdog.FAILURE_THRESHOLD):
            watchdog.record_failure(svc_state)
        self.assertGreater(
            svc_state["cooldown_seconds"], watchdog.INITIAL_COOLDOWN_S,
        )
        watchdog.record_success(svc_state)
        self.assertEqual(svc_state["cooldown_seconds"], watchdog.INITIAL_COOLDOWN_S)


class TestHealthCheckLogic(WatchdogTestBase):

    @patch("watchdog.check_port", return_value=True)
    @patch("watchdog.check_http", return_value=(True, "HTTP 200"))
    def test_http_healthy(self, mock_http, mock_port):
        import watchdog
        config = watchdog.get_config()
        ok, detail = watchdog.deep_health_check("test_svc", config["test_svc"])
        self.assertTrue(ok)
        self.assertIn("200", detail)

    @patch("watchdog.check_port", return_value=False)
    def test_http_port_not_listening(self, mock_port):
        import watchdog
        config = watchdog.get_config()
        ok, detail = watchdog.deep_health_check("test_svc", config["test_svc"])
        self.assertFalse(ok)
        self.assertIn("not listening", detail)

    @patch("watchdog.check_process", return_value=(True, "PID 1234"))
    def test_process_healthy(self, mock_proc):
        import watchdog
        _write_config(self.config_dir, PROCESS_CONFIG)
        config = watchdog.get_config()
        ok, detail = watchdog.deep_health_check("bg_worker", config["bg_worker"])
        self.assertTrue(ok)
        self.assertIn("PID", detail)

    @patch("watchdog.check_process", return_value=(False, "no matching process"))
    def test_process_down(self, mock_proc):
        import watchdog
        _write_config(self.config_dir, PROCESS_CONFIG)
        config = watchdog.get_config()
        ok, detail = watchdog.deep_health_check("bg_worker", config["bg_worker"])
        self.assertFalse(ok)


class TestRunCheck(WatchdogTestBase):

    @patch("watchdog.restart_service", return_value=(True, "restarted ok"))
    @patch("watchdog.deep_health_check", return_value=(False, "port not listening"))
    @patch("watchdog.emit_health_event")
    def test_unhealthy_triggers_restart(self, mock_emit, mock_check, mock_restart):
        import watchdog
        config = watchdog.get_config()
        state = watchdog.load_state()
        results = watchdog.run_check(config, state)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["action"], "restarted")
        mock_restart.assert_called_once()

    @patch("watchdog.deep_health_check", return_value=(True, "HTTP 200"))
    @patch("watchdog.emit_health_event")
    def test_healthy_no_action(self, mock_emit, mock_check):
        import watchdog
        config = watchdog.get_config()
        state = watchdog.load_state()
        results = watchdog.run_check(config, state)
        self.assertEqual(results[0]["action"], "none")
        self.assertTrue(results[0]["healthy"])

    @patch("watchdog.deep_health_check", return_value=(True, "HTTP 200"))
    @patch("watchdog.emit_health_event")
    def test_recovered_after_previous_failure(self, mock_emit, mock_check):
        import watchdog
        config = watchdog.get_config()
        state = watchdog.load_state()
        svc_state = watchdog.ensure_service_state(state, "test_svc")
        svc_state["consecutive_failures"] = 2
        results = watchdog.run_check(config, state)
        self.assertEqual(results[0]["action"], "recovered")


class TestStatePersistence(WatchdogTestBase):

    def test_save_and_load_roundtrip(self):
        import watchdog
        state = watchdog.load_state()
        svc_state = watchdog.ensure_service_state(state, "test_svc")
        watchdog.record_failure(svc_state)
        watchdog.save_state(state)

        reloaded = watchdog.load_state()
        self.assertEqual(reloaded["services"]["test_svc"]["consecutive_failures"], 1)
        self.assertIsNotNone(reloaded["updated_at"])

    def test_missing_state_file_returns_default(self):
        import watchdog
        state = watchdog.load_state()
        self.assertIn("services", state)
        self.assertEqual(len(state["services"]), 0)


class TestCLI(WatchdogTestBase):

    @patch("watchdog.deep_health_check", return_value=(True, "HTTP 200"))
    @patch("watchdog.emit_health_event")
    def test_check_json_output(self, mock_emit, mock_check):
        import io
        import watchdog
        old_stdout = sys.stdout
        sys.stdout = captured = io.StringIO()
        try:
            ret = watchdog.main(["check", "--json"])
        finally:
            sys.stdout = old_stdout
        output = captured.getvalue()
        parsed = json.loads(output)
        self.assertTrue(parsed["ok"])
        self.assertEqual(len(parsed["results"]), 1)
        self.assertEqual(ret, 0)

    @patch("watchdog.deep_health_check", return_value=(True, "HTTP 200"))
    def test_status_command(self, mock_check):
        import io
        import watchdog
        old_stdout = sys.stdout
        sys.stdout = captured = io.StringIO()
        try:
            ret = watchdog.main(["status"])
        finally:
            sys.stdout = old_stdout
        output = captured.getvalue()
        self.assertIn("test_svc", output)
        self.assertEqual(ret, 0)


if __name__ == "__main__":
    unittest.main()
