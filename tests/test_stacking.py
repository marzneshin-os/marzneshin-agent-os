"""Unit tests for Jev + Claude Stacking Engine (scripts/lib/stacking.py)."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(1, str(REPO / "scripts"))

import unittest
from sim.fakes.laya import LayaFake
from scripts.lib.stacking import evaluate_stack, StackingVerdict


class TestStackingEngine(unittest.TestCase):
    def setUp(self):
        self.fake_laya = LayaFake(world="sim")

    def test_fast_path_when_confident(self):
        prompt = "I was billed twice. Please refund the duplicate invoice."
        verdict = evaluate_stack(
            prompt,
            criteria=["billing", "technical", "general"],
            threshold=0.85,
            adapter=self.fake_laya,
        )
        self.assertTrue(verdict.fast_path)
        self.assertFalse(verdict.escalate)
        self.assertEqual(verdict.decision, "billing")
        self.assertEqual(verdict.cost_savings_ratio, "440x")
        self.assertGreater(verdict.tokens_saved, 0)
        self.assertGreater(verdict.est_cost_saved_usd, 0.0)

    def test_escalate_when_uncertain(self):
        prompt = "Vague request without clear keywords."
        self.fake_laya.confidence_override = 0.50
        verdict = evaluate_stack(
            prompt,
            criteria=["billing", "technical", "general"],
            threshold=0.99,
            adapter=self.fake_laya,
        )
        self.assertTrue(verdict.escalate)
        self.assertFalse(verdict.fast_path)

    def test_fail_closed_on_error(self):
        self.fake_laya.fail_next_execute = True
        verdict = evaluate_stack(
            "Some prompt",
            criteria=["billing", "technical"],
            adapter=self.fake_laya,
        )
        self.assertTrue(verdict.escalate)
        self.assertFalse(verdict.fast_path)


if __name__ == "__main__":
    unittest.main()
