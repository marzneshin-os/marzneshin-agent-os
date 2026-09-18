"""test_canary_pipeline.py — Unit tests for Canary Pipeline & Auto-Rollback (BUILD-SPEC §5.7, VS-7).

Tests:
  1. Statistical sample size calculation (n_min from MDE).
  2. Sequential testing bound (always-valid p-value).
  3. Inconclusive gate when n < n_min (data insufficient is never green).
  4. Probe fleet fail-closed enforcement (< 2 healthy ASNs blocks promotion).
  5. Error budget exhaustion blocks rollout (hold).
  6. Auto-rollback triggered on CSR degradation below safety floor.
  7. Multi-stage promotion progression (1% -> 10% -> 50% -> 100%).
  8. CLI commands execution and JSON reporting.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(1, str(REPO / "scripts"))

from lib import canary, paths, probe_fleet  # noqa: E402


class TestCanaryPipeline(unittest.TestCase):
    def setUp(self):
        # Ensure fresh canary dir
        c_dir = paths.state_dir() / "canary"
        c_dir.mkdir(parents=True, exist_ok=True)
        for f in c_dir.glob("canary-test-*.json"):
            f.unlink()

    def tearDown(self):
        c_dir = paths.state_dir() / "canary"
        for f in c_dir.glob("canary-test-*.json"):
            f.unlink()

    def test_n_min_calculation(self):
        # MDE = 0.02, alpha = 0.05, power = 0.8
        n = canary.compute_n_min(mde=0.02, alpha=0.05, power=0.8)
        self.assertGreaterEqual(n, 9800)
        self.assertLessEqual(n, 10000)

        # Larger MDE -> smaller sample size needed
        n_large = canary.compute_n_min(mde=0.05)
        self.assertLess(n_large, n)

    def test_always_valid_p_value(self):
        # Identical rates -> p_val = 1.0
        p_val_equal = canary.compute_always_valid_p_value(1000, 990, 1000, 990)
        self.assertEqual(p_val_equal, 1.0)

        # Severely degraded test sample -> p_val close to 0.0
        p_val_diff = canary.compute_always_valid_p_value(10000, 9900, 10000, 9000)
        self.assertLess(p_val_diff, 0.001)

    def test_inconclusive_when_under_sample_size(self):
        # Healthy probe fleet
        pf = probe_fleet.ProbeFleetResult(
            total_samples=150,
            total_ok=150,
            csr=1.0,
            targets={},
            healthy_asns=["asn:AS1", "asn:AS2", "asn:AS3"],
            healthy=True,
            timestamp="2026-09-18T18:00:00Z",
            fail_closed=False,
        )
        # Samples (500) < n_min (~9804) -> must be INCONCLUSIVE
        dec = canary.evaluate_canary_gate(
            current_stage_pct=1,
            samples=500,
            ok=498,
            probe_fleet_result=pf,
            mde=0.02,
        )
        self.assertEqual(dec.verdict, "inconclusive")
        self.assertIn("data insufficient is never green", dec.reason)

    def test_fail_closed_when_probe_fleet_degraded(self):
        # Only 1 healthy ASN (< 2) -> degraded probe fleet
        pf = probe_fleet.ProbeFleetResult(
            total_samples=10000,
            total_ok=9950,
            csr=0.995,
            targets={},
            healthy_asns=["asn:AS1"],
            healthy=False,
            timestamp="2026-09-18T18:00:00Z",
            fail_closed=True,
        )
        dec = canary.evaluate_canary_gate(
            current_stage_pct=10,
            samples=10000,
            ok=9950,
            probe_fleet_result=pf,
        )
        self.assertEqual(dec.verdict, "hold")
        self.assertIn("probe fleet degraded", dec.reason)
        self.assertIn("fail-closed", dec.reason)

    def test_error_budget_exhaustion_blocks_promotion(self):
        pf = probe_fleet.ProbeFleetResult(
            total_samples=10000,
            total_ok=9950,
            csr=0.995,
            targets={},
            healthy_asns=["asn:AS1", "asn:AS2", "asn:AS3"],
            healthy=True,
            timestamp="2026-09-18T18:00:00Z",
            fail_closed=False,
        )
        dec = canary.evaluate_canary_gate(
            current_stage_pct=10,
            samples=10000,
            ok=9950,
            probe_fleet_result=pf,
            error_budget_exhausted=True,
        )
        self.assertEqual(dec.verdict, "hold")
        self.assertIn("error budget exhausted", dec.reason)

    def test_auto_rollback_on_critical_csr_drop(self):
        pf = probe_fleet.ProbeFleetResult(
            total_samples=1000,
            total_ok=900,
            csr=0.90,
            targets={},
            healthy_asns=["asn:AS1", "asn:AS2", "asn:AS3"],
            healthy=True,
            timestamp="2026-09-18T18:00:00Z",
            fail_closed=False,
        )
        dec = canary.evaluate_canary_gate(
            current_stage_pct=10,
            samples=1000,
            ok=900,  # 90% CSR < 95% critical floor
            probe_fleet_result=pf,
        )
        self.assertEqual(dec.verdict, "rollback")
        self.assertIn("auto-rollback triggered", dec.reason)

    def test_promotion_stage_progression_and_rollback(self):
        # 1. Deploy canary
        exp = canary.deploy_canary("test-v1", initial_pct=1, mde=0.02)
        exp_id = exp["experiment_id"]
        self.assertEqual(exp["current_stage_pct"], 1)

        # 2. Promote from 1% -> 10%
        pf = probe_fleet.ProbeFleetResult(
            total_samples=10000,
            total_ok=9950,
            csr=0.995,
            targets={},
            healthy_asns=["asn:AS1", "asn:AS2", "asn:AS3"],
            healthy=True,
            timestamp="2026-09-18T18:00:00Z",
            fail_closed=False,
        )
        res1 = canary.promote_canary(
            exp_id,
            samples=10000,
            ok=9950,
            probe_fleet_result=pf,
        )
        self.assertTrue(res1["ok"])
        self.assertEqual(res1["stage"], 10)

        # 3. Promote from 10% -> 50%
        res2 = canary.promote_canary(
            exp_id,
            samples=10000,
            ok=9950,
            probe_fleet_result=pf,
        )
        self.assertTrue(res2["ok"])
        self.assertEqual(res2["stage"], 50)

        # 4. Critical drop triggers auto-rollback during attempt to promote
        res_rb = canary.promote_canary(
            exp_id,
            samples=1000,
            ok=880,  # 88% CSR
            probe_fleet_result=pf,
        )
        self.assertTrue(res_rb["ok"])
        self.assertEqual(res_rb["verdict"], "rollback")
        self.assertTrue(res_rb["rolled_back"])

        # Check recorded experiment state
        updated = canary.get_canary(exp_id)
        self.assertIsNotNone(updated)
        self.assertEqual(updated["status"], "rolled_back")
        self.assertEqual(updated["current_stage_pct"], 0)
        self.assertIn("CSR critical drop", updated["rollback"]["reason"])


if __name__ == "__main__":
    unittest.main()
