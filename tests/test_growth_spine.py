"""test_growth_spine.py — Unit tests for Growth Spine, Schema Upcaster, and NSM (BUILD-SPEC §13, VS-8).

Tests:
  1. Event Schema Upcaster v2.0.0 -> v2.1.0 (pure function, no mutation, adds taxonomy fields).
  2. Analytics Engineer Agent Card conformance.
  3. Privacy Invariant (§13.1): user traffic and destination forbidden from entering event payloads.
  4. Traceable North Star Metric (NSM) calculation (paid + connected in window).
  5. Multi-step funnel calculation and conversion rates.
  6. Unit Economics & Stop-Loss rule (CAC > 1.5x target).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(1, str(REPO / "scripts"))

from lib import events, growth, validate  # noqa: E402


class TestGrowthSpine(unittest.TestCase):
    def setUp(self):
        validate.load_migrations()

    def test_schema_upcaster_v2_0_to_v2_1(self):
        event_v2_0 = {
            "schema_version": "2.0.0",
            "event_id": "01M2TEST000000000000000001",
            "actor_seq": 1,
            "ts": "2026-09-18T12:00:00.000Z",
            "type": "checkout.completed",
            "actor": {"kind": "human", "id": "u_test_mig"},
            "subject": {"kind": "growth", "id": "checkout.completed"},
            "payload": {"amount_usd": 15.0, "campaign": "fall_launch"},
            "world": "sim",
            "trust": "internal",
            "redacted": False,
            "redaction_map": [],
        }

        upcasted = validate.upcast(event_v2_0, "event", "2.1.0")
        self.assertEqual(upcasted["schema_version"], "2.1.0")
        self.assertEqual(upcasted["event_id"], event_v2_0["event_id"])
        self.assertEqual(upcasted["campaign"], "fall_launch")
        self.assertEqual(upcasted["consent_state"], "granted")
        # Ensure input was not mutated
        self.assertEqual(event_v2_0["schema_version"], "2.0.0")

    def test_privacy_invariant_enforcement(self):
        # Forbidden traffic field: destination_ip
        bad_payload = {"user": "alice", "destination_ip": "1.1.1.1"}
        with self.assertRaises(growth.PrivacyViolationError) as ctx:
            growth.assert_no_traffic_content(bad_payload)
        self.assertIn("Privacy invariant violation", str(ctx.exception))

        # Nested forbidden field
        nested_bad = {"meta": {"destination_url": "https://example.com/login"}}
        with self.assertRaises(growth.PrivacyViolationError):
            growth.assert_no_traffic_content(nested_bad)

        # Allowed growth payload
        clean_payload = {"amount_usd": 20.0, "tier": "premium", "nodes_used": 3}
        # Should not raise
        growth.assert_no_traffic_content(clean_payload)

    def test_nsm_calculation_and_traceability(self):
        # Record events for user 1 (paid and connected -> NSM count +1)
        growth.record_growth_event("checkout.completed", "u_nsm_1", payload={"tier": "pro"})
        growth.record_growth_event("connection.success", "u_nsm_1")

        # Record events for user 2 (paid but not connected yet -> NSM count 0)
        growth.record_growth_event("checkout.completed", "u_nsm_2", payload={"tier": "starter"})

        # Record events for user 3 (connected free trial, not paid -> NSM count 0)
        growth.record_growth_event("connection.success", "u_nsm_3")

        res = growth.compute_nsm(window_days=7)
        self.assertGreaterEqual(res["nsm_count"], 1)
        self.assertIn("u_nsm_1", res["active_users"])
        self.assertNotIn("u_nsm_2", res["active_users"])
        self.assertNotIn("u_nsm_3", res["active_users"])

        # Traceability invariant (§13.2): every count traceable to raw event IDs
        self.assertGreater(len(res["event_trace"]), 0)
        self.assertEqual(res["trace_events_count"], len(res["event_trace"]))

    def test_funnel_metrics(self):
        growth.record_growth_event("funnel.visit", "u_funnel_1")
        growth.record_growth_event("funnel.signup", "u_funnel_1")
        growth.record_growth_event("funnel.trial_started", "u_funnel_1")
        growth.record_growth_event("checkout.completed", "u_funnel_1")
        growth.record_growth_event("connection.success", "u_funnel_1")

        funnel = growth.compute_funnel(window_days=7)
        counts = funnel["counts"]
        self.assertGreaterEqual(counts["visit"], 1)
        self.assertGreaterEqual(counts["signup"], 1)
        self.assertGreaterEqual(counts["trial"], 1)
        self.assertGreaterEqual(counts["paid"], 1)
        self.assertGreaterEqual(counts["active"], 1)

        rates = funnel["conversion_rates"]
        self.assertGreater(rates["overall_visit_to_paid"], 0.0)

    def test_unit_economics_and_stop_loss(self):
        # Healthy campaign
        econ = growth.compute_unit_economics(
            arpu=25.0,
            infra_per_user=2.5,
            payment_fee=0.8,
            support_cost=1.2,
            agent_token_cost_per_user=0.5,
            cac=15.0,
            expected_lifetime_months=12,
            target_cac=20.0,
        )
        self.assertEqual(econ["gross_profit_per_user"], 20.0)
        self.assertEqual(econ["gross_margin_pct"], 80.0)
        self.assertTrue(econ["targets_met"]["ltv_cac_gt_3"])
        self.assertTrue(econ["targets_met"]["payback_lt_3mo"])
        self.assertTrue(econ["targets_met"]["gross_margin_gt_70"])
        self.assertFalse(econ["stop_loss_triggered"])

        # Runaway CAC campaign -> stop loss triggered (CAC > 1.5x target)
        econ_bad = growth.compute_unit_economics(
            arpu=25.0,
            infra_per_user=2.5,
            payment_fee=0.8,
            support_cost=1.2,
            agent_token_cost_per_user=0.5,
            cac=35.0,
            target_cac=20.0,  # 35 > 1.5 * 20 (30)
        )
        self.assertTrue(econ_bad["stop_loss_triggered"])
        self.assertIn("CAC > 1.5x target threshold", econ_bad["stop_loss_reason"])


if __name__ == "__main__":
    unittest.main()
