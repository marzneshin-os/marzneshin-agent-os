"""test_tier0_agents.py — Unit tests for Tier 0 Agents (BUILD-SPEC §10.1, VS-5).

Tests:
  1. Complete Agent Cards in agents/cards/ against agent-card.schema.json and cross-card rules.
  2. Budget reservation and settlement lifecycle (G8).
  3. Handoff Guardian: handoff verification and operational continuity scoring.
  4. Adversarial Reviewer: independent lineage, separation of duties, and critical path rejection.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(1, str(REPO / "scripts"))

from lib import adversarial_reviewer, budget, handoff_guardian, paths, validate  # noqa: E402
from lib.atomic import read_json  # noqa: E402
import yaml  # noqa: E402


class TestAgentCards(unittest.TestCase):
    """Verify all 7 Tier 0 Agent Cards exist, validate against schema, and obey cross-card laws."""

    EXPECTED_TIER_0 = {
        "orchestrator",
        "config-engineer",
        "infra-sre",
        "qa-gate",
        "security-compliance",
        "handoff-guardian",
        "adversarial-reviewer",
    }

    def test_all_seven_tier0_cards_exist(self):
        cards_dir = paths.agent_cards_dir()
        self.assertTrue(cards_dir.exists(), "agents/cards directory must exist")
        found_ids = set()
        for f in cards_dir.glob("*.yaml"):
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if data and data.get("tier") == 0:
                found_ids.add(data.get("id"))
        missing = self.EXPECTED_TIER_0 - found_ids
        self.assertFalse(missing, f"Missing Tier 0 Agent Cards: {missing}")

    def test_all_cards_validate_against_schema(self):
        cards_dir = paths.agent_cards_dir()
        for f in cards_dir.glob("*.yaml"):
            card = yaml.safe_load(f.read_text(encoding="utf-8"))
            res = validate.validate(card, "agent-card", strict=True)
            self.assertTrue(res.ok, f"{f.name} failed schema validation: {res.errors}")

    def test_cross_card_invariants_and_counter_kpis(self):
        cards_dir = paths.agent_cards_dir()
        seen_owns: dict[str, str] = {}
        for f in cards_dir.glob("*.yaml"):
            card = yaml.safe_load(f.read_text(encoding="utf-8"))
            cid = card["id"]
            # I13: counter_kpi non-empty and counter_kpi_owner != id
            self.assertTrue(card.get("counter_kpi"), f"{cid}: counter_kpi is empty")
            self.assertNotEqual(card.get("counter_kpi_owner"), cid,
                                f"{cid}: counter_kpi_owner == id violates I13")
            # §3.4: sim_scenarios_required non-empty
            self.assertTrue(card.get("sim_scenarios_required"),
                            f"{cid}: sim_scenarios_required is empty")
            # I17: no owns overlap
            for pattern in card.get("owns", []):
                self.assertNotIn(pattern, seen_owns,
                                 f"{cid}: owns {pattern} overlaps with {seen_owns.get(pattern)}")
                seen_owns[pattern] = cid
            # Mutating capability idempotency
            idem = card.get("idempotency", {}) or {}
            for cap in card.get("capabilities", []):
                if cap.split(".")[0] in {"read", "analytics"}:
                    continue
                self.assertIn(cap, idem,
                              f"{cid}: mutating capability {cap!r} has no idempotency class")


class TestBudgetLifecycle(unittest.TestCase):
    """Verify budget reservation and settlement."""

    def test_budget_reserve_and_settle(self):
        res = budget.reserve(
            agent="config-engineer",
            tier=0,
            task_id="T-BUDGET-TEST-1",
            model="claude-haiku-4-5",
            est_tokens_in=1000,
            est_tokens_out=500,
        )
        self.assertIn("reservation_id", res)
        self.assertGreater(res["est_usd"], 0.0)

        # Settle actual usage
        settlement = budget.settle(
            reservation_id=res["reservation_id"],
            agent="config-engineer",
            tier=0,
            task_id="T-BUDGET-TEST-1",
            model="claude-haiku-4-5",
            tokens_in=800,
            tokens_out=400,
        )
        self.assertGreater(settlement["usd"], 0.0)


class TestHandoffGuardian(unittest.TestCase):
    """Verify Handoff Guardian verification and continuity scoring."""

    def test_handoff_verification_passes_on_current_handoff(self):
        res = handoff_guardian.verify_handoff()
        self.assertTrue(res["ok"], f"HANDOFF.md verification failed: {res.get('reasons')}")
        self.assertEqual(res["score"], 1.0)
        self.assertIsNotNone(res["updated"])
        self.assertIsNotNone(res["by"])
        self.assertIsNotNone(res["slice"])

    def test_continuity_score_is_green(self):
        score_res = handoff_guardian.compute_continuity_score()
        self.assertEqual(score_res["verdict"], "PASS")
        self.assertGreaterEqual(score_res["score"], 0.8)
        self.assertEqual(score_res["factors"]["handoff_freshness"], 1.0)
        self.assertEqual(score_res["factors"]["receipt_coverage"], 1.0)
        self.assertEqual(score_res["factors"]["zero_zombies"], 1.0)
        self.assertEqual(score_res["factors"]["baseline_health"], 1.0)


class TestAdversarialReviewer(unittest.TestCase):
    """Verify independent adversarial review, separation of duties, and critical path protection."""

    def test_self_review_is_rejected(self):
        res = adversarial_reviewer.review_change(
            author="adversarial-reviewer",
            author_lineage="gpt-4o/adversarial@1",
            intent="review my own code",
            changes=["scripts/lib/policy.py"],
        )
        self.assertEqual(res["verdict"], adversarial_reviewer.ReviewVerdict.REJECT)
        self.assertTrue(any("separation of duties" in r for r in res["reasons"]))

    def test_lineage_collusion_is_rejected(self):
        res = adversarial_reviewer.review_change(
            author="adversarial-clone",
            author_lineage="gpt-4o/clone@1",
            intent="review change from same model family",
            changes=["scripts/lib/test.py"],
        )
        self.assertEqual(res["verdict"], adversarial_reviewer.ReviewVerdict.REJECT)
        self.assertTrue(any("lineage collusion" in r for r in res["reasons"]))

    def test_critical_path_relaxation_is_rejected(self):
        res = adversarial_reviewer.review_change(
            author="coder",
            author_lineage="claude-3-5/coder@1",
            intent="relax test gate",
            changes=["scripts/verify.py"],
            diff_text="diff: skip verify tests by setting strict = False",
        )
        self.assertEqual(res["verdict"], adversarial_reviewer.ReviewVerdict.REJECT)
        self.assertTrue(any("critical gate relaxation" in r for r in res["reasons"]))

    def test_benign_change_with_independent_lineage_is_approved(self):
        res = adversarial_reviewer.review_change(
            author="coder",
            author_lineage="claude-3-5/coder@1",
            intent="add clean helper function",
            changes=["scripts/lib/helpers.py"],
            diff_text="def add(a, b): return a + b",
        )
        self.assertEqual(res["verdict"], adversarial_reviewer.ReviewVerdict.APPROVE)
        self.assertEqual(len(res["reasons"]), 0)


if __name__ == "__main__":
    unittest.main()
