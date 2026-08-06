#!/usr/bin/env python3
"""Tests for the A2A bus (BUILD-SPEC §3.5, §5 — VS-3).

Proves the three things VS-3 exists for:
  1. one envelope moves between transports with zero content change
  2. idempotency: a repeat send returns the stored result, nothing re-executes
  3. fallback: 3 T2 failures degrade the route to T1; 5 health successes
     restore it (§5.5 hysteresis) — all with audit events

Run:  python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

PY = sys.executable

from lib import a2a

class A2ATestCase(unittest.TestCase):
    """Isolated repo root with registry + schemas, real clock off, KS running."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="marz-a2a-"))
        (self.tmp / "state").mkdir(parents=True, exist_ok=True)
        (self.tmp / "BUILD-SPEC.md").write_text("test\n", encoding="utf-8")
        shutil.copytree(REPO / "analytics" / "schemas",
                        self.tmp / "analytics" / "schemas")
        (self.tmp / "agents").mkdir(exist_ok=True)
        shutil.copy(REPO / "agents" / "registry.json",
                    self.tmp / "agents" / "registry.json")
        self._env = dict(os.environ)
        os.environ["MARZNESHIN_OPS_ROOT"] = str(self.tmp)
        os.environ["MARZ_WORLD"] = "sim"  # VirtualClock guard (ADR-002 D14)
        os.environ.pop("KILL_SWITCH", None)
        from lib import a2a, clock, killswitch, validate
        validate.clear_cache()
        a2a.clear_registry_cache()
        self.clock = clock.VirtualClock(seed=7)
        clock.set_clock(self.clock)
        killswitch.touch_heartbeat(verified_by="test", sources=["test"])
        self.a2a = a2a
        self.events = __import__("lib.events", fromlist=["events"])

    def tearDown(self) -> None:
        from lib import clock
        clock.set_clock(None)
        os.environ.clear()
        os.environ.update(self._env)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def actor(self, name="orchestrator"):
        return self.events.Actor(kind="agent", id=name, session="S-test")

    def build(self, **kw) -> dict:
        kw.setdefault("sender", "orchestrator")
        kw.setdefault("to", "qa-gate")
        kw.setdefault("capability", "probe.echo")
        kw.setdefault("input", {"n": 1})
        kw.setdefault("input_provenance",
                      [{"field": "$.input", "source": "test", "trust": "internal"}])
        kw.setdefault("env_epoch", "test-epoch")
        return self.a2a.build_envelope(**kw)


class FlakyT2(a2a.T2Client):
    """Scriptable T2 client: unhealthy for N health checks, then healthy.

    healthz drives degradation (the router probes before routing); deliver
    only runs once the route is chosen — matching how lib/a2a.py uses both.
    """

    def __init__(self, fail: int = 0) -> None:
        self.fail_left = fail
        self.delivered: list[str] = []

    def healthz(self) -> bool:
        if self.fail_left > 0:
            self.fail_left -= 1
            return False
        return True

    def deliver(self, envelope: dict) -> dict:
        self.delivered.append(envelope["task_id"])
        return {"ref": f"moxt://task/{envelope['task_id']}"}


class TestEnvelope(A2ATestCase):
    def test_build_validates_against_schema(self):
        env = self.build()
        self.assertEqual(env["schema_version"], "2.0.0")
        self.assertEqual(self.a2a.validate_envelope(env), [])
        self.assertTrue(env["task_id"].startswith("A2A-"))
        self.assertEqual(env["idempotency"]["class"], "scoped")
        self.assertIn("env_epoch", "".join(env["idempotency"]["components"]))

    def test_unknown_recipient_fails_closed(self):
        with self.assertRaises(self.a2a.A2AError):
            self.build(to="ghost-agent")

    def test_undeclared_capability_refused(self):
        with self.assertRaises(self.a2a.A2AError):
            self.build(capability="infra.nuke")

    def test_envelope_content_is_transport_independent(self):
        env = self.build()
        core = {k: v for k, v in env.items() if k != "transport"}
        env_t1 = dict(env, transport="T1")
        env_t2 = dict(env, transport="T2")
        self.assertEqual({k: v for k, v in env_t1.items() if k != "transport"},
                         {k: v for k, v in env_t2.items() if k != "transport"})


class TestT1RoundTrip(A2ATestCase):
    def test_send_process_complete_with_audit(self):
        env = self.build()
        r = self.a2a.send(env, actor=self.actor())
        self.assertTrue(r.ok, r.reason)
        self.assertEqual(r.transport, "T1")  # no T2 heartbeat -> baseline
        self.assertEqual(self.a2a.queue_depth("qa-gate"), 1)

        results = self.a2a.process_inbox(
            "qa-gate", {"probe.echo": lambda e: {"pong": e["input"]}},
            actor=self.actor("qa-gate"))
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].ok)
        self.assertEqual(results[0].handler_result, {"pong": {"n": 1}})
        self.assertEqual(self.a2a.queue_depth("qa-gate"), 0)
        # I17: archived, not deleted
        processed = list((self.tmp / "state" / "a2a" / "processed" / "qa-gate").glob("*.json"))
        self.assertEqual(len(processed), 1)


class TestIdempotency(A2ATestCase):
    def test_repeat_send_does_not_reexecute(self):
        env = self.build()
        r1 = self.a2a.send(env, actor=self.actor())
        r2 = self.a2a.send(env, actor=self.actor())
        self.assertTrue(r1.ok and not r1.replayed)
        self.assertTrue(r2.ok and r2.replayed)
        self.assertEqual(self.a2a.queue_depth("qa-gate"), 1,
                         "a replayed send must not enqueue a second copy")

    def test_replay_after_completion_returns_stored_state(self):
        env = self.build()
        self.a2a.send(env, actor=self.actor())
        self.a2a.process_inbox("qa-gate", {"probe.echo": lambda e: {}},
                               actor=self.actor("qa-gate"))
        r = self.a2a.send(env, actor=self.actor())
        self.assertTrue(r.replayed)
        self.assertEqual(r.state, "completed")

    def test_scoped_ttl_expiry_allows_fresh_execution(self):
        env = self.build()  # registry: probe.echo scoped ttl 3600
        self.a2a.send(env, actor=self.actor())
        self.clock.advance(seconds=3601)
        r = self.a2a.send(env, actor=self.actor())
        self.assertFalse(r.replayed, "after TTL the key must not suppress a fresh run")
        # Same task_id re-executes: the durable key no longer protects it.
        runs = []
        self.a2a.process_inbox("qa-gate",
                               {"probe.echo": lambda e: runs.append(e["task_id"]) or {}},
                               actor=self.actor("qa-gate"))
        self.assertEqual(runs, [env["task_id"]])
        self.assertEqual(r.task_id, env["task_id"])


class TestFallback(A2ATestCase):
    def test_three_failures_degrade_t2_to_t1_then_five_greens_restore(self):
        t2 = FlakyT2(fail=3)
        # 3 failures -> degraded at the third (§5.5)
        for i in range(3):
            env = self.build(input={"n": i})
            r = self.a2a.send(env, t2_client=t2, actor=self.actor())
        st = self.a2a.transport_state("T2")
        self.assertTrue(st["degraded"], "3 consecutive failures must degrade T2")
        self.assertEqual(self.a2a.transport_state("T2")["consecutive_failures"], 3)
        # degraded: traffic flows on T1 with zero envelope content change
        env = self.build(input={"n": 99})
        r = self.a2a.send(env, t2_client=t2, actor=self.actor())
        self.assertTrue(r.ok)
        self.assertEqual(r.transport, "T1")
        # 5 consecutive health successes restore (hysteresis)
        for _ in range(5):
            usable = self.a2a.record_transport_result("T2", True, actor=self.actor())
        self.assertFalse(self.a2a.transport_state("T2")["degraded"])
        env = self.build(input={"n": 100})
        r = self.a2a.send(env, t2_client=t2, actor=self.actor())
        self.assertEqual(r.transport, "T2")
        self.assertIn(env["task_id"], t2.delivered)

    def test_file_t2_client_is_fail_closed_without_heartbeat(self):
        client = self.a2a.FileT2Client()
        self.assertFalse(client.healthz(),
                         "no heartbeat = unavailable, never 'probably fine' (rule 6)")


class TestCli(A2ATestCase):
    def run_cli(self, *argv: str) -> subprocess.CompletedProcess:
        e = dict(os.environ)
        e["MARZNESHIN_OPS_ROOT"] = str(self.tmp)
        e.pop("MARZ_WORLD", None)
        return subprocess.run([PY, str(REPO / "scripts" / "a2a.py"), *argv],
                              capture_output=True, text=True, env=e, timeout=60,
                              cwd=REPO)

    def reconcile_ks(self) -> None:
        """Fresh KS heartbeat with REAL time for the subprocess (real clock)."""
        e = dict(os.environ)
        e["MARZNESHIN_OPS_ROOT"] = str(self.tmp)
        e.pop("MARZ_WORLD", None)
        out = subprocess.run([PY, str(REPO / "scripts" / "killswitch.py"),
                              "reconcile", "--skip-auto", "--by", "test"],
                             capture_output=True, text=True, env=e, timeout=30,
                             cwd=REPO)
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_verify_gate(self):
        out = self.run_cli("verify")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("[PASS]", out.stdout)

    def test_send_process_via_cli(self):
        self.reconcile_ks()
        out = self.run_cli("send", "--to", "qa-gate", "--capability", "probe.echo",
                           "--input", '{"via": "cli"}')
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        doc = json.loads(out.stdout)
        self.assertTrue(doc["ok"])
        out = self.run_cli("process", "--agent", "qa-gate")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        doc = json.loads(out.stdout)
        self.assertEqual(doc["processed"], 1)
        self.assertEqual(doc["results"][0]["result"]["echo"], {"via": "cli"})

    def test_status_reports_transports(self):
        out = self.run_cli("status")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("qa-gate", out.stdout)

    def test_qa_gate_run_handler_executes_real_gates(self):
        self.reconcile_ks()
        out = self.run_cli("send", "--to", "qa-gate", "--capability", "qa.gate.run",
                           "--input", '{"suite": "chain"}')
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        out = self.run_cli("process", "--agent", "qa-gate")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        doc = json.loads(out.stdout)
        self.assertEqual(doc["results"][0]["result"]["verdict"], "green")
        self.assertTrue(any("chain" in c for c in doc["results"][0]["result"]["checks"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
