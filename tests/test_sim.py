#!/usr/bin/env python3
"""Tests for the simulation harness and adapter contract (BUILD-SPEC §16.1).

The contract suite runs against all nine fakes (§4: a fake that diverges from
its real adapter makes the simulation worthless). The harness tests prove the
two claims VS-2 exists for: 72 virtual hours run in seconds, and a seed makes
a run exactly reproducible.

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
# REPO must precede scripts/: both expose a top-level name `sim` (the package
# sim/ and the runner scripts/sim.py). scripts-first makes `import sim` resolve
# to the runner, which then fails on `from sim import actors` (circular).
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

PY = sys.executable


class TestAdapterContract(unittest.TestCase):
    """Every fake passes the same contract suite its real adapter will (§4)."""

    def _check(self, name: str) -> None:
        from adapters.contract import run_contract
        from sim.fakes import build_fakes
        from sim.world import World, WorldConfig

        world = World(WorldConfig(nodes=2, users=100), seed=7)
        fakes = build_fakes(world, seed=7)
        fake = fakes[name]
        results = run_contract(lambda: fake, fake.capabilities())
        failed = [r for r in results if not r.ok]
        self.assertEqual(failed, [],
                         f"{name} contract failures: "
                         f"{[(r.check, r.detail) for r in failed]}")

    def test_github(self):
        self._check("github")

    def test_moxt(self):
        self._check("moxt")

    def test_clickup(self):
        self._check("clickup")

    def test_marzneshin(self):
        self._check("marzneshin")

    def test_payments(self):
        self._check("payments")

    def test_analytics(self):
        self._check("analytics")

    def test_messaging(self):
        self._check("messaging")

    def test_observability(self):
        self._check("observability")

    def test_vault(self):
        self._check("vault")

    def test_omniroute(self):
        self._check("omniroute")

    def test_out_of_band_alert_is_recorded(self):
        """§11.2 hard requirement: the OOB channel actually works in sim."""
        from sim.fakes import build_fakes
        from sim.world import World, WorldConfig

        world = World(WorldConfig(nodes=1, users=10), seed=1)
        fakes = build_fakes(world, seed=1)
        r = fakes["messaging"].execute(
            "out_of_band_alert", {"severity": "critical", "text": "drill"},
            idem_key="oob:1", idem_class="forever", dry_run=False,
            deadline=_deadline(), provenance=[])
        self.assertTrue(r.ok)
        self.assertEqual(len(fakes["messaging"].oob_alerts), 1)


def _deadline():
    from datetime import datetime, timedelta, timezone
    return datetime.now(timezone.utc) + timedelta(minutes=5)


class TestCircuitBreaker(unittest.TestCase):
    def test_opens_after_threshold_and_recovers(self):
        from adapters.base import AdapterError, CircuitBreaker, CircuitOpen
        cb = CircuitBreaker(threshold=5, reset_after_s=0.01)
        for _ in range(5):
            cb.on_failure()
        with self.assertRaises(CircuitOpen):
            cb.before_call()
        import time
        time.sleep(0.02)
        cb.before_call()  # half-open probe allowed
        cb.on_success()
        self.assertEqual(cb.state, "closed")

    def test_failures_reset_on_success(self):
        from adapters.base import CircuitBreaker
        cb = CircuitBreaker(threshold=3)
        cb.on_failure(); cb.on_failure()
        cb.on_success()
        cb.on_failure(); cb.on_failure()
        self.assertEqual(cb.state, "closed")


class TestSimHarness(unittest.TestCase):
    def _run(self, scenario: str, seed: int) -> dict:
        env = dict(os.environ)
        env["MARZNESHIN_OPS_ROOT"] = str(REPO)
        out = subprocess.run(
            [PY, str(REPO / "scripts" / "sim.py"), "run",
             str(REPO / "sim" / "scenarios" / f"{scenario}.yaml"),
             "--seed", str(seed), "--json"],
            capture_output=True, text=True, env=env, timeout=120, cwd=REPO)
        self.assertEqual(out.returncode, 0,
                         f"{scenario} seed {seed} failed:\n{out.stdout}\n{out.stderr}")
        payload = json.loads(out.stdout)
        return payload["reports"][0]

    def test_72_virtual_hours_run_in_seconds(self):
        r = self._run("node_outage", 11)
        self.assertEqual(r["duration"]["virtual_hours"], 72)
        self.assertLess(r["duration"]["wall_clock_s"], 60,
                        "72 virtual hours must compress into seconds (§16 DoD)")
        self.assertEqual(r["result"], "pass")

    def test_seed_makes_run_exactly_reproducible(self):
        a = self._run("agent_crash_mid_task", 42)
        b = self._run("agent_crash_mid_task", 42)
        strip = lambda r: {k: v for k, v in r.items() if k not in ("duration", "artifacts")}
        self.assertEqual(strip(a), strip(b), "same seed must replay exactly (§16)")

    def test_crash_scenario_produces_tombstone_and_chain_stays_valid(self):
        r = self._run("agent_crash_mid_task", 11)
        self.assertGreater(r["receipts"]["total"], 1)
        self.assertGreater(r["receipts"]["crash_rate"], 0.0,
                           "a killed mid-task agent must leave a crashed receipt (G5)")
        self.assertTrue(r["receipts"]["chain_ok"], "receipt chain must stay valid (I15)")
        self.assertEqual(r["metrics"]["receipt_coverage"], 1.0)
        self.assertEqual(r["metrics"]["duplicate_work"], 0)

    def test_prompt_injection_never_grants_above_l1(self):
        r = self._run("prompt_injection", 11)
        self.assertEqual(r["metrics"]["guardrail_breaches"], 0,
                         "I16 violated: untrusted content drove autonomy above L1")

    def test_all_scenarios_pass_on_all_base_seeds(self):
        env = dict(os.environ)
        env["MARZNESHIN_OPS_ROOT"] = str(REPO)
        out = subprocess.run(
            [PY, str(REPO / "scripts" / "sim.py"), "run", "--all",
             "--seeds", "11,27,43"],
            capture_output=True, text=True, env=env, timeout=900, cwd=REPO)
        self.assertEqual(out.returncode, 0,
                         f"suite red:\n{out.stdout[-2000:]}\n{out.stderr[-1000:]}")
        # 17 scenarios x 3 seeds (11 through session 7 + clock_skew,
        # control_room_down, gateway_down, metric_gaming,
        # config_canary_regression, probe_fleet_down)
        expected_passes = len(list((REPO / "sim" / "scenarios").glob("*.yaml"))) * 3
        self.assertEqual(out.stdout.count("[PASS]"), expected_passes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
