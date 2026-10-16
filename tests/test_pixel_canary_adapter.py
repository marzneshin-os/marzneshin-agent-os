"""Tests for Pixel Canary Adapter (BUILD-SPEC §4)."""

import unittest
from datetime import datetime, timezone, timedelta
from adapters.pixel_canary import PixelCanaryAdapter


class TestPixelCanaryAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = PixelCanaryAdapter(world="sim")
        self.deadline = datetime.now(timezone.utc) + timedelta(seconds=30)

    def test_healthz(self):
        health = self.adapter.healthz()
        self.assertTrue(health.ok)
        self.assertIn("Pixel Canary", health.detail)

    def test_capabilities(self):
        caps = self.adapter.capabilities()
        self.assertIn("check_environment", caps)
        self.assertIn("chat_completion", caps)
        self.assertIn("evaluate_code", caps)
        self.assertIn("calculate_cost_savings", caps)
        self.assertIn("get_model_card", caps)

    def test_check_environment(self):
        res = self.adapter.execute(
            "check_environment",
            {},
            idem_key="test-check-env",
            deadline=self.deadline,
        )
        self.assertTrue(res.ok)
        self.assertEqual(res.data["model_id"], "stealth/pixel-canary")
        self.assertEqual(res.data["cost"], "FREE")
        self.assertEqual(res.data["eval_pass4_score"], 0.90)

    def test_get_model_card(self):
        res = self.adapter.execute(
            "get_model_card",
            {},
            idem_key="test-model-card",
            deadline=self.deadline,
        )
        self.assertTrue(res.ok)
        self.assertEqual(res.data["name"], "Pixel Canary")
        self.assertEqual(res.data["benchmarks"]["nextjs_agent_evals_pass4"], 0.90)
        self.assertEqual(res.data["benchmarks"]["vs_gpt6_astra"], "Tied (90%)")

    def test_calculate_cost_savings(self):
        res = self.adapter.execute(
            "calculate_cost_savings",
            {"tasks_count": 1000},
            idem_key="test-savings",
            deadline=self.deadline,
        )
        self.assertTrue(res.ok)
        self.assertEqual(res.data["tasks_count"], 1000)
        self.assertEqual(res.data["pixel_canary_cost_usd"], 0.0)
        self.assertEqual(res.data["gpt6_astra_cost_usd"], 890.0)
        self.assertEqual(res.data["savings_vs_gpt6_usd"], 890.0)
        self.assertEqual(res.data["percent_saved"], 100.0)

    def test_evaluate_code(self):
        valid_nextjs_code = """
        'use server';
        export async function submitForm(formData: FormData) {
            const email = formData.get('email');
            return { ok: true, email };
        }
        """
        res = self.adapter.execute(
            "evaluate_code",
            {"code": valid_nextjs_code, "task_type": "server_actions"},
            idem_key="test-eval-code",
            deadline=self.deadline,
        )
        self.assertTrue(res.ok)
        self.assertEqual(res.data["status"], "PASS")
        self.assertTrue(res.data["checks"]["has_server_directive"])
        self.assertTrue(res.data["checks"]["has_async_action"])

    def test_chat_completion_sim(self):
        res = self.adapter.execute(
            "chat_completion",
            {"prompt": "Create a server action"},
            idem_key="test-chat",
            dry_run=True,
            deadline=self.deadline,
        )
        self.assertTrue(res.ok)
        self.assertEqual(res.data["model"], "stealth/pixel-canary")
        self.assertEqual(res.data["cost_usd"], 0.0)
        self.assertIn("use server", res.data["content"])

    def test_idempotency_replay(self):
        res1 = self.adapter.execute(
            "get_model_card",
            {},
            idem_key="repeatable-key-1",
            deadline=self.deadline,
        )
        self.assertTrue(res1.ok)
        self.assertFalse(res1.replayed)

        res2 = self.adapter.execute(
            "get_model_card",
            {},
            idem_key="repeatable-key-1",
            deadline=self.deadline,
        )
        self.assertTrue(res2.ok)
        self.assertTrue(res2.replayed)


if __name__ == "__main__":
    unittest.main()
