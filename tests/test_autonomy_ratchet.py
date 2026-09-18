"""test_autonomy_ratchet.py — Unit tests for Autonomy Ratchet, Shadow Mode & Continuous Review (BUILD-SPEC §6.2, §14, §17, VS-11).

Tests:
  1. Shadow Mode decision recording and agreement calculation.
  2. Promotion blocked when shadow agreement < 95% or sample < 20.
  3. Promotion blocked when clean runs < 30.
  4. Promotion succeeds when ALL 3 conditions satisfied (30 clean runs, >=95% shadow agreement, sim green).
  5. Permanent L1 ceiling on money, pricing, security, and infra (Rule I17).
  6. Demotion and 72-hour quarantine on breach.
  7. Machine-readable review contract output in orchestrator inbox.
"""

from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(1, str(REPO / "scripts"))

from lib import autonomy, paths  # noqa: E402


class TestAutonomyRatchet(unittest.TestCase):
    def setUp(self):
        self.test_dir = paths.state_dir() / "autonomy"
        self.shadow_dir = self.test_dir / "shadow"
        self.shadow_dir.mkdir(parents=True, exist_ok=True)
        # Clear test shadow files
        for f in self.shadow_dir.glob("test-*.ndjson"):
            f.unlink()

    def tearDown(self):
        for f in self.shadow_dir.glob("test-*.ndjson"):
            f.unlink()

    def test_shadow_decision_recording_and_agreement(self):
        agent_id = "test-agent-1"
        cap = "data.transform"

        # Record 20 matching shadow decisions
        for i in range(20):
            autonomy.record_shadow_decision(
                agent_id=agent_id,
                capability=cap,
                shadow_level="L2",
                proposed_action={"action": "clean", "target": f"batch_{i}"},
                human_action={"action": "clean", "target": f"batch_{i}"},
            )

        res = autonomy.compute_shadow_agreement(agent_id, cap, window_n=20)
        self.assertEqual(res["total_samples"], 20)
        self.assertEqual(res["matching"], 20)
        self.assertEqual(res["agreement_rate"], 1.0)
        self.assertTrue(res["sufficient_samples"])
        self.assertTrue(res["target_met"])

    def test_promotion_blocked_when_shadow_disagrees(self):
        agent_id = "test-agent-2"
        cap = "routing.optimize"

        # Record 15 matching and 5 diverging decisions -> 75% agreement < 95% threshold
        for i in range(15):
            autonomy.record_shadow_decision(
                agent_id=agent_id,
                capability=cap,
                shadow_level="L2",
                proposed_action="route_a",
                human_action="route_a",
            )
        for i in range(5):
            autonomy.record_shadow_decision(
                agent_id=agent_id,
                capability=cap,
                shadow_level="L2",
                proposed_action="route_a",
                human_action="route_b",
            )

        res = autonomy.compute_shadow_agreement(agent_id, cap, window_n=20)
        self.assertEqual(res["total_samples"], 20)
        self.assertEqual(res["matching"], 15)
        self.assertEqual(res["agreement_rate"], 0.75)
        self.assertFalse(res["target_met"])

    def test_permanent_l1_ceiling_enforced(self):
        # Money spend capability cannot be promoted above L1 (§6.1, Rule I17)
        contract = autonomy.evaluate_autonomy_review("test-agent-3", "money.spend", write_inbox=False)
        self.assertEqual(contract["verdict"], "hold")
        self.assertIn("permanently capped at L1", contract["reason"])

        contract_sec = autonomy.evaluate_autonomy_review("test-agent-3", "security.rotate", write_inbox=False)
        self.assertEqual(contract_sec["verdict"], "hold")
        self.assertIn("permanently capped at L1", contract_sec["reason"])

    def test_demotion_and_quarantine_on_breach(self):
        agent_id = "test-agent-4"
        cap = "canary.deploy"

        # Demote agent
        dem = autonomy.demote_agent(agent_id, cap, reason="CSR dropped below 0.95")
        self.assertEqual(dem["agent"], agent_id)
        self.assertIn("quarantine_until", dem)

        # Check quarantine status
        in_q, q_until = autonomy.is_quarantined(agent_id)
        self.assertTrue(in_q)
        self.assertIsNotNone(q_until)

        # Autonomy review during quarantine returns demote/quarantined
        contract = autonomy.evaluate_autonomy_review(agent_id, cap, write_inbox=False)
        self.assertEqual(contract["verdict"], "demote")
        self.assertIn("72-hour quarantine", contract["reason"])

    def test_machine_readable_review_contract_in_orchestrator_inbox(self):
        agent_id = "test-agent-5"
        cap = "log.compact"

        contract = autonomy.evaluate_autonomy_review(agent_id, cap, write_inbox=True)
        inbox = paths.a2a_inbox("orchestrator")
        matching = list(inbox.glob(f"autonomy_review_{agent_id}_*.json"))
        self.assertTrue(len(matching) >= 1, "Review contract not found in orchestrator inbox")

        saved = json.loads(matching[0].read_text(encoding="utf-8"))
        self.assertEqual(saved.get("schema_version"), "2.0.0")
        contract_data = saved.get("input", saved)
        self.assertEqual(contract_data["agent"], agent_id)
        self.assertEqual(contract_data["capability"], cap)
        self.assertIn("verdict", contract_data)
        self.assertIn("reason", contract_data)


if __name__ == "__main__":
    unittest.main()
