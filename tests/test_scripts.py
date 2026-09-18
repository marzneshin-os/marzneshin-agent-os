#!/usr/bin/env python3
"""End-to-end tests for scripts/ and hooks/ (BUILD-SPEC §16.1).

Every test drives the real CLI as a subprocess against a throwaway repo root
(MARZNESHIN_OPS_ROOT), so the tests exercise the actual contract a worker or
CI job depends on — including exit codes, which are the whole point of a hook.

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
from datetime import timedelta
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
PY = sys.executable


class CliTestCase(unittest.TestCase):
    """Base: an isolated repo root; the real scripts run against it."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="marz-cli-"))
        (self.tmp / "state").mkdir(parents=True, exist_ok=True)
        (self.tmp / "BUILD-SPEC.md").write_text("test\n", encoding="utf-8")
        # A real checkout carries the committed schemas; simulate that so
        # --schemas validates artifacts exactly as CI would.
        shutil.copytree(REPO / "analytics" / "schemas",
                        self.tmp / "analytics" / "schemas")
        self._env = dict(os.environ)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, *argv: str, stdin: str = "", env: dict | None = None,
                timeout: int = 30) -> subprocess.CompletedProcess:
        e = dict(os.environ)
        e["MARZNESHIN_OPS_ROOT"] = str(self.tmp)
        e.pop("KILL_SWITCH", None)
        e.pop("MARZ_WORLD", None)
        if env:
            e.update(env)
        return subprocess.run([PY, str(REPO / argv[0]), *argv[1:]],
                              input=stdin, capture_output=True, text=True,
                              env=e, timeout=timeout, cwd=REPO)

    def bootstrap(self) -> None:
        out = self.run_cli("scripts/fsp.py", "bootstrap", "--agent", "test")
        self.assertEqual(out.returncode, 0, out.stderr)

    def heartbeat(self) -> None:
        """Make the kill switch report RUNNING (fresh clones are UNKNOWN)."""
        out = self.run_cli("scripts/killswitch.py", "reconcile", "--skip-auto",
                           "--by", "test")
        self.assertIn(out.returncode, (0, 1), out.stderr)


# --- fsp.py ----------------------------------------------------------------

class TestFsp(CliTestCase):
    def test_bootstrap_creates_state_and_is_idempotent(self):
        self.bootstrap()
        state_file = self.tmp / "state" / "STATE.json"
        body = json.loads(state_file.read_text())
        self.assertEqual(body["schema_version"], "2.0.0")
        self.assertEqual(body["active_slice"], "VS-1")
        again = self.run_cli("scripts/fsp.py", "bootstrap", "--agent", "test")
        self.assertIn("already exists", again.stdout)

    def test_claim_heartbeat_release_cycle(self):
        self.bootstrap()
        claim = self.run_cli("scripts/fsp.py", "claim", "ws-a", "--agent", "tester")
        self.assertEqual(claim.returncode, 0, claim.stderr)
        self.assertIn("fencing_token=1", claim.stdout)
        beat = self.run_cli("scripts/fsp.py", "heartbeat", "ws-a", "--agent", "tester")
        self.assertEqual(beat.returncode, 0, beat.stderr)
        rel = self.run_cli("scripts/fsp.py", "release", "ws-a", "--agent", "tester")
        self.assertEqual(rel.returncode, 0, rel.stderr)
        # Events exist for each step, in the agent's own partition.
        day_dirs = list((self.tmp / "state" / "events").glob("2*/agent-tester.ndjson"))
        self.assertTrue(day_dirs, "no per-actor event partition written")

    def test_double_claim_by_other_agent_refused(self):
        self.bootstrap()
        self.run_cli("scripts/fsp.py", "claim", "ws-a", "--agent", "first")
        second = self.run_cli("scripts/fsp.py", "claim", "ws-a", "--agent", "second")
        self.assertEqual(second.returncode, 1)
        self.assertIn("held by", second.stderr)


# --- verify.py -------------------------------------------------------------

class TestVerify(CliTestCase):
    def test_all_green_on_bootstrapped_repo(self):
        self.bootstrap()
        out = self.run_cli("scripts/verify.py", "--all")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("GREEN", out.stdout)

    def test_chain_detects_tampering(self):
        self.bootstrap()
        self.heartbeat()
        # Write one real receipt through the lib (via a tiny driver).
        driver = (
            "import sys; sys.path.insert(0, 'scripts')\n"
            "from lib import receipts, clock, ids\n"
            "r = receipts.Receipt(task_id='T-1', agent='a', workstream='ws',"
            " status=receipts.Status.COMPLETE, autonomy_level='L2', intent='i',"
            " reason='r', started_at=clock.iso(), inputs_hash=ids.sha256_str('x'),"
            " verification=[receipts.Verification(check='c', result='pass', evidence='e')],"
            " rollback=receipts.Rollback(method='m', tested=True,"
            " tested_at=clock.iso(), tested_in='sim'))\n"
            "receipts.write(r)\n"
        )
        out = subprocess.run([PY, "-c", driver], cwd=REPO, capture_output=True,
                             text=True, env={**os.environ,
                                             "MARZNESHIN_OPS_ROOT": str(self.tmp)})
        self.assertEqual(out.returncode, 0, out.stderr)
        ok = self.run_cli("scripts/verify.py", "--chain")
        self.assertEqual(ok.returncode, 0, ok.stdout)
        # Tamper with it.
        receipt = next(self.tmp.glob("receipts/2*/*/T-1.json"))
        body = json.loads(receipt.read_text())
        body["intent"] = "TAMPERED"
        receipt.write_text(json.dumps(body, indent=2))
        bad = self.run_cli("scripts/verify.py", "--chain")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("mismatch", bad.stdout)

    def test_lint_clock_catches_wall_clock(self):
        (self.tmp / "scripts").mkdir(exist_ok=True)
        # lint runs against the REAL repo; instead verify the linter flags a
        # planted violation file inside the real scripts tree, then remove it.
        planted = REPO / "scripts" / "_lint_clock_probe.py"
        planted.write_text("import time\nnow = time.time()\n", encoding="utf-8")
        try:
            out = self.run_cli("scripts/verify.py", "--lint-clock")
            self.assertEqual(out.returncode, 1)
            self.assertIn("_lint_clock_probe.py", out.stdout)
        finally:
            planted.unlink()


# --- compact.py ------------------------------------------------------------

class TestCompact(CliTestCase):
    def test_compact_produces_valid_state(self):
        self.bootstrap()
        self.run_cli("scripts/fsp.py", "claim", "ws-a", "--agent", "tester")
        out = self.run_cli("scripts/compact.py")
        self.assertEqual(out.returncode, 0, out.stderr)
        body = json.loads((self.tmp / "state" / "STATE.json").read_text())
        self.assertIn("compacted_from", body)
        self.assertIn("actor_seq_watermarks", body["compacted_from"])
        self.assertIn("ws-a", body["workstreams"])
        check = self.run_cli("scripts/verify.py", "--schemas")
        self.assertEqual(check.returncode, 0, check.stdout)

    def test_compact_derives_active_slice_from_transition_event(self):
        """ADR-008. A slice change mid-phase must be derivable from the log
        alone, or STATE goes stale and the only 'fix' is hand-editing it —
        which §3.1 forbids and the pre-tool hook blocks. Cold restore must
        rebuild the *current* slice, not the one the session opened with.
        """
        self.bootstrap()
        emitted = self.run_cli(
            "scripts/fsp.py", "slice", "VS-9", "--agent", "tester",
            "--phase", "P2-test", "--note", "moved on")
        self.assertEqual(emitted.returncode, 0, emitted.stderr)

        out = self.run_cli("scripts/compact.py")
        self.assertEqual(out.returncode, 0, out.stderr)
        body = json.loads((self.tmp / "state" / "STATE.json").read_text())
        self.assertEqual(body["active_slice"], "VS-9")
        self.assertEqual(body["phase"], "P2-test")
        check = self.run_cli("scripts/verify.py", "--schemas")
        self.assertEqual(check.returncode, 0, check.stdout)

    def test_slice_transition_is_rejected_without_the_lease(self):
        """Fencing applies to narrative state too: an agent that does not hold
        the workstream must not be able to move the whole phase pointer."""
        self.bootstrap()
        self.run_cli("scripts/fsp.py", "claim", "agentic-core", "--agent", "holder")
        out = self.run_cli("scripts/fsp.py", "slice", "VS-9", "--agent", "outsider")
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("lease", (out.stderr + out.stdout).lower())


# --- reaper.py -------------------------------------------------------------

class TestReaper(CliTestCase):
    def test_zombie_lease_gets_tombstone_and_burned_token(self):
        self.bootstrap()
        self.run_cli("scripts/fsp.py", "claim", "ws-dead", "--agent", "ghost")
        # Age the lease past TTL by rewriting its timestamps.
        lock = self.tmp / "state" / "locks" / "ws-dead.lock.json"
        body = json.loads(lock.read_text())
        body["acquired_at"] = "2020-01-01T00:00:00.000Z"
        body["heartbeat_at"] = "2020-01-01T00:00:00.000Z"
        lock.write_text(json.dumps(body, indent=2))

        dry = self.run_cli("scripts/reaper.py", "--dry-run")
        self.assertEqual(dry.returncode, 1, dry.stdout)  # found work, changed nothing
        self.assertTrue(lock.exists(), "dry run must not revoke")

        real = self.run_cli("scripts/reaper.py")
        self.assertEqual(real.returncode, 1, real.stdout)
        self.assertFalse(lock.exists(), "live lock file must be revoked")
        self.assertTrue((self.tmp / "state" / "locks" / "ws-dead.revoked.json").exists(),
                        "revocation record (burned fencing token) missing")
        tombs = list(self.tmp.glob("receipts/2*/*/T-UNKNOWN-ws-dead-*.json"))
        self.assertTrue(tombs, "no tombstone receipt written")
        body = json.loads(tombs[0].read_text())
        self.assertEqual(body["status"], "crashed")

    def test_no_zombies_is_quiet(self):
        self.bootstrap()
        out = self.run_cli("scripts/reaper.py")
        self.assertEqual(out.returncode, 0)
        self.assertIn("nothing to reap", out.stdout)


# --- killswitch.py CLI -----------------------------------------------------

class TestKillSwitchCli(CliTestCase):
    def test_verify_drills_all_five_paths(self):
        out = self.run_cli("scripts/killswitch.py", "verify")
        self.assertEqual(out.returncode, 0, out.stdout)
        for path in ("K1:state/KILL", "K2:env/KILL_SWITCH", "K3:moxt/control-room",
                     "K4:cli", "K5:auto", "K0:fail-closed-on-fresh-clone",
                     "K0:stale-verdict-decays-to-unknown",
                     "K1:corrupt-file-fails-closed"):
            self.assertIn(f"[PASS] {path}", out.stdout)

    def test_fresh_clone_is_fail_closed(self):
        out = self.run_cli("scripts/killswitch.py", "status")
        self.assertEqual(out.returncode, 2, out.stdout)  # UNKNOWN == halt
        self.assertIn("unknown", out.stdout.lower())

    def test_engage_blocks_then_release_clears(self):
        self.bootstrap()
        self.heartbeat()
        ok = self.run_cli("scripts/killswitch.py", "status")
        self.assertEqual(ok.returncode, 0, ok.stdout)
        self.run_cli("scripts/killswitch.py", "engage", "global",
                     "--reason", "drill", "--by", "test")
        killed = self.run_cli("scripts/killswitch.py", "status")
        self.assertEqual(killed.returncode, 1)
        self.run_cli("scripts/killswitch.py", "release", "global", "--by", "test")
        cleared = self.run_cli("scripts/killswitch.py", "status")
        self.assertEqual(cleared.returncode, 0, cleared.stdout)


# --- hooks -----------------------------------------------------------------

class TestHooks(CliTestCase):
    def _hook_env(self) -> dict:
        return {"MARZ_AGENT_ID": "tester", "MARZ_SESSION": "S-test"}

    def test_session_start_on_fresh_clone_guides_bootstrap(self):
        out = self.run_cli("hooks/session_start.py", stdin='{"source":"startup"}',
                           env=self._hook_env())
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("bootstrap", out.stdout)

    def test_pre_tool_blocks_secret_in_args(self):
        payload = json.dumps({"tool_name": "Bash", "tool_input": {
            "command": "curl -H 'Authorization: ghp_" + "a" * 36 + "' x"}})
        out = self.run_cli("hooks/pre_tool.py", stdin=payload, env=self._hook_env())
        self.assertEqual(out.returncode, 2)
        self.assertIn("secret", out.stdout)

    def test_pre_tool_blocks_hand_edit_of_append_only_store(self):
        self.bootstrap()
        self.heartbeat()
        payload = json.dumps({"tool_name": "Write", "tool_input": {
            "file_path": str(REPO / "receipts" / "2026" / "07" / "T-x.json"),
            "content": "{}"}})
        out = self.run_cli("hooks/pre_tool.py", stdin=payload, env=self._hook_env())
        self.assertEqual(out.returncode, 2)
        self.assertIn("append-only", out.stdout)

    def test_pre_tool_fail_closed_when_kill_switch_unknown(self):
        self.bootstrap()  # no heartbeat -> UNKNOWN
        payload = json.dumps({"tool_name": "Write", "tool_input": {
            "file_path": str(REPO / "docs" / "x.md"), "content": "hi"}})
        out = self.run_cli("hooks/pre_tool.py", stdin=payload, env=self._hook_env())
        self.assertEqual(out.returncode, 2)
        self.assertIn("fail-closed", out.stdout)

    def test_pre_tool_allows_clean_write_when_running(self):
        self.bootstrap()
        self.heartbeat()
        payload = json.dumps({"tool_name": "Write", "tool_input": {
            "file_path": str(REPO / "docs" / "x.md"), "content": "hi"}})
        out = self.run_cli("hooks/pre_tool.py", stdin=payload, env=self._hook_env())
        self.assertEqual(out.returncode, 0, out.stdout)

    def test_post_tool_flags_secret_in_output(self):
        payload = json.dumps({"tool_name": "Bash",
                              "tool_response": "key: sk-ant-" + "b" * 24})
        out = self.run_cli("hooks/post_tool.py", stdin=payload, env=self._hook_env())
        self.assertEqual(out.returncode, 2)
        self.assertIn("rotate", out.stdout)

    def test_task_complete_requires_receipt(self):
        self.bootstrap()
        out = self.run_cli("hooks/task_complete.py", stdin='{}',
                           env={**self._hook_env(), "MARZ_TASK_ID": "T-NOPE"})
        self.assertEqual(out.returncode, 2)
        self.assertIn("no receipt", out.stdout)

    def test_stop_blocks_on_held_lease(self):
        self.bootstrap()
        self.run_cli("scripts/fsp.py", "claim", "ws-held", "--agent", "tester")
        out = self.run_cli("hooks/stop.py", stdin='{}', env=self._hook_env())
        self.assertEqual(out.returncode, 2)
        self.assertIn("still held", out.stdout)

    def test_stop_clean_after_release_and_handoff(self):
        self.bootstrap()
        self.run_cli("scripts/fsp.py", "claim", "ws-held", "--agent", "tester")
        self.run_cli("scripts/fsp.py", "release", "ws-held", "--agent", "tester")
        out = self.run_cli("hooks/stop.py", stdin='{}', env=self._hook_env())
        self.assertEqual(out.returncode, 0, out.stdout)


# --- context_pack.py -------------------------------------------------------

class TestContextPack(CliTestCase):
    def test_generates_pack_with_live_sections(self):
        self.bootstrap()
        self.run_cli("scripts/fsp.py", "claim", "ws-a", "--agent", "tester")
        out = self.run_cli("scripts/context_pack.py")
        self.assertEqual(out.returncode, 0, out.stderr)
        pack = (self.tmp / "CONTEXT-PACK.md").read_text(encoding="utf-8")
        self.assertIn("Kill switch", pack)
        self.assertIn("session protocol", pack)
        self.assertIn("ws-a", pack)


# --- health.py --save-baseline (ADR-009 D46) -------------------------------

class TestHealthSaveBaseline(CliTestCase):
    """Regression (VS-4, ADR-009 D46): a green run that did not execute every
    gate the current floor tracks must NOT be saveable — the old behaviour
    silently rewrote HEALTH-BASELINE.json with only the gates that happened
    to run, erasing `coldrestore` from the floor the first time anyone saved
    from a plain `health.py` run. A gate that quietly weakens the floor is
    the exact defect class ADR-007 was filed against.

    All gates are skipped here, so these run fast and touch nothing outside
    the throwaway root (health.py honours MARZNESHIN_OPS_ROOT, D46).
    """

    BASELINE_REL = ("state", "HEALTH-BASELINE.json")

    def _baseline(self, gates: dict) -> Path:
        f = self.tmp.joinpath(*self.BASELINE_REL)
        f.write_text(json.dumps({"gates": gates}), encoding="utf-8")
        return f

    def _save(self) -> subprocess.CompletedProcess:
        return self.run_cli("scripts/health.py", "--skip-tests", "--skip-verify",
                            "--skip-sim", "--save-baseline")

    def test_refuses_when_a_tracked_gate_did_not_run(self):
        f = self._baseline({"tests": {"passed": 3, "total": 3},
                            "coldrestore": {"passed": 1, "total": 1}})
        before = f.read_text(encoding="utf-8")
        out = self._save()
        self.assertEqual(out.returncode, 1, out.stderr)
        self.assertIn("coldrestore", out.stderr)
        self.assertEqual(f.read_text(encoding="utf-8", ), before,
                         "refused save must leave the floor byte-identical")

    def test_saves_when_nothing_tracked_is_missing(self):
        f = self._baseline({})
        out = self._save()
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("gates", json.loads(f.read_text(encoding="utf-8")))

    def test_saves_when_no_baseline_exists_yet(self):
        f = self.tmp.joinpath(*self.BASELINE_REL)
        out = self._save()
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertTrue(f.exists())


class TestHealthBaselineUnit(unittest.TestCase):
    """Pure-function coverage of the same contract, no subprocess.

    health.py is loaded by file location, NOT via sys.path: inserting
    scripts/ at position 0 makes `import sim` in test_sim resolve to
    scripts/sim.py instead of the sim/ package (circular-import error).
    """

    health: Any = None

    @classmethod
    def setUpClass(cls) -> None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "health", REPO / "scripts" / "health.py")
        assert spec is not None
        assert spec.loader is not None
        cls.health = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.health)

    def test_missing_baseline_gates_lists_exactly_the_unexecuted(self):
        health = self.health
        baseline = {"gates": {"tests": {"passed": 1, "total": 1},
                              "coldrestore": {"passed": 1, "total": 1}}}
        self.assertEqual(
            health.missing_baseline_gates(["tests", "verify", "sim"], baseline),
            ["coldrestore"])
        self.assertEqual(
            health.missing_baseline_gates(
                ["tests", "verify", "sim", "coldrestore"], baseline), [])
        self.assertEqual(health.missing_baseline_gates([], {}), [])

    def test_save_baseline_raises_on_missing_gate(self):
        health = self.health
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d) / "HEALTH-BASELINE.json"
            tmp.write_text(json.dumps(
                {"gates": {"coldrestore": {"passed": 1, "total": 1}}}),
                encoding="utf-8")
            with mock.patch.object(health, "BASELINE", tmp):
                with self.assertRaises(health.BaselineCoverageError) as ctx:
                    health.save_baseline(
                        [{"gate": "tests", "passed": 3, "total": 3}], "VS-4")
                self.assertIn("coldrestore", str(ctx.exception))
                # ...and a covered run writes the file.
                health.save_baseline(
                    [{"gate": "tests", "passed": 3, "total": 3},
                     {"gate": "coldrestore", "passed": 1, "total": 1}], "VS-4")
                body = json.loads(tmp.read_text(encoding="utf-8"))
                self.assertEqual(body["gates"]["coldrestore"]["passed"], 1)
                self.assertEqual(body["active_slice"], "VS-4")


# --- succession.py (§11.1, VS-4) --------------------------------------------

class TestSuccession(CliTestCase):
    """The executable §11.1 flow: TRIGGER -> FREEZE -> REVOKE -> RECONSTRUCT
    -> REASSIGN -> VERIFY -> REPORT, against a throwaway root."""

    def setUp(self) -> None:
        super().setUp()
        # The flow reads and amends the A2A registry (REVOKE/REASSIGN steps).
        (self.tmp / "agents").mkdir(exist_ok=True)
        shutil.copy(REPO / "agents" / "registry.json",
                    self.tmp / "agents" / "registry.json")
        self.bootstrap()

    def _open_task(self, task_id: str = "T-OPEN-1") -> None:
        """An open task on the log: started, never completed (G5 condition)."""
        code = (
            "import sys; sys.path.insert(0, 'scripts');"
            "from lib import events;"
            "a = events.Actor(kind='agent', id='config-engineer', session='S-DEAD');"
            f"events.emit('task.started', a, events.Subject(kind='task', id='{task_id}'),"
            " {'workstream': 'sim-config'})"
        )
        env = {**os.environ, "MARZNESHIN_OPS_ROOT": str(self.tmp)}
        env.pop("KILL_SWITCH", None)
        env.pop("MARZ_WORLD", None)
        out = subprocess.run([PY, "-c", code], capture_output=True, text=True,
                             env=env, cwd=REPO, timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr)

    def _run_flow(self, *extra: str) -> subprocess.CompletedProcess:
        return self.run_cli("scripts/succession.py", "run",
                            "--agent", "config-engineer",
                            "--workstream", "sim-config",
                            "--trigger", "member_removed", *extra)

    def test_full_flow_freezes_revokes_reassigns_and_reports(self):
        self.run_cli("scripts/fsp.py", "claim", "sim-config", "--agent", "config-engineer")
        self._open_task()
        out = self._run_flow()
        self.assertEqual(out.returncode, 0, out.stderr)
        for step in ("FREEZE", "REVOKE", "RECONSTRUCT", "REASSIGN", "VERIFY", "REPORT"):
            self.assertIn(step, out.stdout)
        # FREEZE: lease file gone, revocation marker written, token burned.
        self.assertFalse((self.tmp / "state" / "locks" / "sim-config.lock.json").exists())
        self.assertTrue((self.tmp / "state" / "locks" / "sim-config.revoked.json").exists())
        # REVOKE: registry marks the member revoked; REASSIGN: standby present.
        reg = json.loads((self.tmp / "agents" / "registry.json").read_text())
        self.assertTrue(reg["agents"]["config-engineer"].get("revoked"))
        self.assertIn("config-engineer-standby", reg["agents"])
        # FREEZE receipt: the open task is closed as ABANDONED, not crashed —
        # a member removal is an administrative fact, not a crash (crash_rate
        # must not move for it).
        receipt = json.loads((self.tmp / "receipts").glob("*/*/T-OPEN-1.json").__next__()
                             .read_text())
        self.assertEqual(receipt["status"], "abandoned")
        # REPORT: artifact on disk + succession.completed on the log.
        reports = list((self.tmp / "artifacts" / "succession").glob("*.json"))
        self.assertTrue(reports, "no succession report artifact written")
        body = json.loads(reports[0].read_text())
        self.assertEqual(body["reassignment"]["successor"], "config-engineer-standby")
        self.assertLess(body["reassignment"]["autonomy"],  # one level lower (§10.5)
                        body["reassignment"]["predecessor_autonomy"] + 1)
        ev_files = list((self.tmp / "state" / "events").glob("2*/system-succession.ndjson"))
        self.assertTrue(ev_files, "no succession event partition")
        types = [json.loads(ln)["type"] for ln in ev_files[0].read_text().splitlines()]
        self.assertIn("succession.completed", types)
        self.assertIn("succession.frozen", types)

    def test_flow_without_open_lease_or_tasks_still_completes(self):
        out = self._run_flow()
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("REPORT", out.stdout)

    def test_dry_run_changes_nothing(self):
        self.run_cli("scripts/fsp.py", "claim", "sim-config", "--agent", "config-engineer")
        out = self._run_flow("--dry-run")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertTrue((self.tmp / "state" / "locks" / "sim-config.lock.json").exists(),
                        "dry-run must not revoke the lease")
        self.assertFalse((self.tmp / "artifacts" / "succession").exists(),
                         "dry-run must not write a report artifact")

    def test_scan_no_pending_exits_0(self):
        out = self.run_cli("scripts/succession.py", "scan")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("no pending", out.stdout)

    def test_scan_processes_offboarding_json_and_archives(self):
        self.run_cli("scripts/fsp.py", "claim", "sim-config", "--agent", "config-engineer")
        offboarding_data = [
            {
                "agent": "config-engineer",
                "workstream": "sim-config",
                "trigger": "member_removed",
                "reason": "Offboarding test"
            }
        ]
        (self.tmp / "state" / "OFFBOARDING.json").write_text(json.dumps(offboarding_data), encoding="utf-8")
        out = self.run_cli("scripts/succession.py", "scan")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertFalse((self.tmp / "state" / "OFFBOARDING.json").exists(), "OFFBOARDING.json should be moved to archive")
        archived = list((self.tmp / "state" / "archive" / "offboarding").glob("offboarding-*.json"))
        self.assertTrue(archived, "Archive file not found")


# --- escrow.py (§11.2, VS-4) ------------------------------------------------

class TestEscrow(CliTestCase):
    """The encrypted recovery bundle: a non-technical human must be able to
    stop or hand over the system from it (§11.2). Fail-closed rules: no
    passphrase -> no bundle at all (an unencrypted map of every access path
    is itself a sensitive artifact); drift between the bundled RECOVERY.md
    and the repo's is a verification failure, not a warning."""

    PASS = "correct horse battery staple (test)"

    def setUp(self) -> None:
        super().setUp()
        (self.tmp / "RECOVERY.md").write_text("# RECOVERY test doc\n", encoding="utf-8")
        (self.tmp / "CODEOWNERS").write_text("configs/pricing/** @owner\n", encoding="utf-8")
        (self.tmp / "agents").mkdir(exist_ok=True)
        shutil.copy(REPO / "agents" / "registry.json", self.tmp / "agents" / "registry.json")
        self.bootstrap()

    def _build(self, passphrase: str | None = PASS) -> subprocess.CompletedProcess:
        env = {}
        if passphrase is not None:
            env["MARZ_ESCROW_PASSPHRASE"] = passphrase
        else:
            os.environ.pop("MARZ_ESCROW_PASSPHRASE", None)
        return self.run_cli("scripts/escrow.py", "build", env=env)

    def _bundles(self) -> list[Path]:
        d = self.tmp / "state" / "archive" / "escrow"
        return list(d.glob("*.tar.gz.enc")) if d.exists() else []

    @unittest.skipIf(not __import__("shutil").which("openssl"), "openssl not found")
    def test_build_then_verify_roundtrip(self):
        out = self._build()
        self.assertEqual(out.returncode, 0, out.stderr)
        bundles = self._bundles()
        self.assertEqual(len(bundles), 1, "exactly one bundle expected")
        # The bundle must NOT be readable as plain tar (encrypted at rest).
        self.assertNotEqual(bundles[0].read_bytes()[:2], b"\x1f\x8b")
        ver = self.run_cli("scripts/escrow.py", "verify", str(bundles[0]),
                           env={"MARZ_ESCROW_PASSPHRASE": self.PASS})
        self.assertEqual(ver.returncode, 0, ver.stderr + ver.stdout)
    @unittest.skipIf(not __import__("shutil").which("openssl"), "openssl not found")
    def test_build_fails_closed_without_passphrase(self):
        out = self._build(passphrase=None)
        self.assertEqual(out.returncode, 2)
        self.assertIn("MARZ_ESCROW_PASSPHRASE", out.stderr)
        self.assertEqual(self._bundles(), [],
                         "no bundle may exist when encryption is impossible")
    @unittest.skipIf(not __import__("shutil").which("openssl"), "openssl not found")
    def test_verify_detects_recovery_drift(self):
        self.assertEqual(self._build().returncode, 0)
        bundle = self._bundles()[0]
        (self.tmp / "RECOVERY.md").write_text("# RECOVERY changed after build\n",
                                              encoding="utf-8")
        ver = self.run_cli("scripts/escrow.py", "verify", str(bundle),
                           env={"MARZ_ESCROW_PASSPHRASE": self.PASS})
        self.assertEqual(ver.returncode, 1)
        self.assertIn("drift", (ver.stdout + ver.stderr).lower())
    @unittest.skipIf(not __import__("shutil").which("openssl"), "openssl not found")
    def test_verify_with_wrong_passphrase_fails(self):
        self.assertEqual(self._build().returncode, 0)
        bundle = self._bundles()[0]
        ver = self.run_cli("scripts/escrow.py", "verify", str(bundle),
                           env={"MARZ_ESCROW_PASSPHRASE": "wrong"})
        self.assertNotEqual(ver.returncode, 0)


# --- static lint: rollback.tested_in call sites ----------------------------

class TestRollbackTestedInCallSites(unittest.TestCase):
    """Regression (VS-4): coldrestore.py passed tested_in="mirror", which is
    outside the receipt schema enum, so the §11.2 drill could no longer write
    its criterion-4 receipt. lib/receipts.py already refuses the bad value at
    runtime, but nothing stopped a *new* call site from reintroducing it —
    the whole 149/149 suite stayed green while the drill was broken.

    This scans every production call site statically and pins it to the enum
    read from the schema itself, so the schema stays the single source of
    truth (I15/§3.3).
    """

    SCANNED_DIRS = ("scripts", "hooks", "adapters", "sim")

    def _allowed(self) -> set[str]:
        schema = json.loads(
            (REPO / "analytics" / "schemas" / "receipt.schema.json")
            .read_text(encoding="utf-8"))
        node = schema["properties"]["rollback"]["properties"]["tested_in"]
        return set(node["enum"])

    def test_every_tested_in_literal_is_in_the_schema_enum(self):
        import ast

        allowed = self._allowed()
        self.assertTrue(allowed, "schema must publish a tested_in enum")

        offenders: list[str] = []
        for folder in self.SCANNED_DIRS:
            for path in sorted((REPO / folder).rglob("*.py")):
                if "__pycache__" in path.parts:
                    continue
                tree = ast.parse(path.read_text(encoding="utf-8"),
                                 filename=str(path))
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue
                    for kw in node.keywords:
                        if kw.arg != "tested_in":
                            continue
                        if not isinstance(kw.value, ast.Constant):
                            continue          # dynamic — runtime guard covers it
                        if kw.value.value not in allowed:
                            offenders.append(
                                f"{path.relative_to(REPO)}:{kw.lineno} "
                                f"tested_in={kw.value.value!r}")
        self.assertEqual(
            [], offenders,
            "tested_in literals outside the schema enum "
            f"{sorted(allowed)}: " + "; ".join(offenders))


if __name__ == "__main__":
    unittest.main(verbosity=2)
