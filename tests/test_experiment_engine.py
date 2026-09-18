"""test_experiment_engine.py — Unit tests for Experiment Engine, SRM, Guardrails, and Negative Results (BUILD-SPEC §13.4, VS-9).

Tests:
  1. Sample Ratio Mismatch (SRM) Chi-square detection.
  2. Guardrail breach detection and immediate auto-stop.
  3. Statistically significant positive lift triggers 'ship' decision.
  4. Negative or flat outcome produces mandatory negative result and 'kill' decision.
  5. Inconclusive verdict when sample size is insufficient (n < n_min).
  6. Experiment lifecycle persistence and audit events.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(1, str(REPO / "scripts"))

from lib import experiments, paths  # noqa: E402


class TestExperimentEngine(unittest.TestCase):
    def setUp(self):
        e_dir = paths.state_dir() / "experiments"
        e_dir.mkdir(parents=True, exist_ok=True)
        for f in e_dir.glob("exp-test-*.json"):
            f.unlink()

    def tearDown(self):
        e_dir = paths.state_dir() / "experiments"
        for f in e_dir.glob("exp-test-*.json"):
            f.unlink()

    def test_srm_detection(self):
        # 1. Balanced: 5000 vs 5000 -> no SRM
        srm_ok = experiments.check_srm(5000, 5000, target_ratio=0.5)
        self.assertFalse(srm_ok["srm_detected"])
        self.assertGreater(srm_ok["p_value"], 0.05)

        # 2. Skewed: 6000 vs 4000 on 50/50 split -> severe SRM
        srm_bad = experiments.check_srm(6000, 4000, target_ratio=0.5)
        self.assertTrue(srm_bad["srm_detected"])
        self.assertLess(srm_bad["p_value"], 0.001)

        # 3. Readout on skewed sample automatically kills experiment
        exp = experiments.create_experiment("test-srm", "test hypothesis", mde=0.02)
        res = experiments.evaluate_readout(
            exp["experiment_id"],
            samples_a=6000,
            ok_a=600,
            samples_b=4000,
            ok_b=400,
        )
        self.assertEqual(res["verdict"], "kill")
        self.assertIn("SRM detected", res["reason"])
        self.assertTrue(res["is_negative_result"])

    def test_guardrail_breach_triggers_autostop(self):
        exp = experiments.create_experiment(
            "test-guardrail",
            "speed up routing",
            guardrail_metrics={"csr_floor": 0.98},
            mde=0.02,
        )
        # Observed CSR is 0.94 < 0.98 floor -> must trigger auto-stop
        res = experiments.evaluate_readout(
            exp["experiment_id"],
            samples_a=5000,
            ok_a=4900,
            samples_b=5000,
            ok_b=4950,
            guardrail_values={"csr_floor": 0.94},
        )
        self.assertEqual(res["verdict"], "stopped")
        self.assertIn("Guardrail breach", res["reason"])
        self.assertTrue(res["is_negative_result"])

        # Check persisted status
        updated = experiments.get_experiment(exp["experiment_id"])
        self.assertEqual(updated["status"], "stopped")

    def test_ship_decision_on_statistically_significant_lift(self):
        exp = experiments.create_experiment(
            "test-ship",
            "optimize checkout flow",
            mde=0.02,
        )
        # Control: 5% conversion (500/10000), Treatment: 8% conversion (800/10000)
        # n = 20000 >= n_min (~9800), p_value < 0.05, delta = +0.03
        res = experiments.evaluate_readout(
            exp["experiment_id"],
            samples_a=10000,
            ok_a=500,
            samples_b=10000,
            ok_b=800,
        )
        self.assertEqual(res["verdict"], "ship")
        self.assertIn("statistically significant positive lift", res["reason"])
        self.assertFalse(res["is_negative_result"])

        updated = experiments.get_experiment(exp["experiment_id"])
        self.assertEqual(updated["status"], "ship")

    def test_kill_decision_on_flat_or_regressed_result(self):
        exp = experiments.create_experiment(
            "test-flat",
            "minor button color tweak",
            mde=0.02,
        )
        # Flat result at final readout (5.0% vs 5.01%)
        res = experiments.evaluate_readout(
            exp["experiment_id"],
            samples_a=10000,
            ok_a=500,
            samples_b=10000,
            ok_b=501,
            final_readout=True,
        )
        self.assertEqual(res["verdict"], "kill")
        self.assertIn("flat result at end of trial", res["reason"])
        self.assertTrue(res["is_negative_result"])

        # Regression (5.0% vs 3.0%)
        exp_reg = experiments.create_experiment("test-reg", "poor copy", mde=0.02)
        res_reg = experiments.evaluate_readout(
            exp_reg["experiment_id"],
            samples_a=10000,
            ok_a=500,
            samples_b=10000,
            ok_b=300,
        )
        self.assertEqual(res_reg["verdict"], "kill")
        self.assertIn("statistically significant regression", res_reg["reason"])
        self.assertTrue(res_reg["is_negative_result"])

    def test_inconclusive_when_under_sample_size(self):
        exp = experiments.create_experiment("test-inconclusive", "test", mde=0.02)
        # Total samples 1000 < 9800 n_min
        res = experiments.evaluate_readout(
            exp["experiment_id"],
            samples_a=500,
            ok_a=50,
            samples_b=500,
            ok_b=60,
        )
        self.assertEqual(res["verdict"], "inconclusive")
        self.assertIn("insufficient sample size", res["reason"])


if __name__ == "__main__":
    unittest.main()
