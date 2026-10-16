"""Contract and unit tests for AWSBedrockAdapter (adapters/aws_bedrock.py)."""

import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
import sim
if str(REPO / "scripts") not in sys.path:
    sys.path.append(str(REPO / "scripts"))

from adapters.contract import run_contract
from adapters.aws_bedrock import AWSBedrockAdapter
from sim.fakes.aws_bedrock import AWSBedrockFake


class TestAWSBedrockAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = AWSBedrockAdapter(world="sim")
        self.fake = AWSBedrockFake(world="sim")
        self.deadline = datetime.now(timezone.utc) + timedelta(seconds=30)

    def test_healthz(self):
        h = self.adapter.healthz()
        self.assertTrue(h.ok)
        self.assertIn("bedrock", h.detail.lower())

    def test_capabilities(self):
        caps = self.adapter.capabilities()
        self.assertIn("bedrock_invoke_model", caps)
        self.assertIn("bedrock_converse", caps)
        self.assertIn("bedrock_check_credits", caps)
        self.assertIn("bedrock_rotate_account", caps)
        self.assertIn("bedrock_onboarding_checklist", caps)

    def test_fake_contract(self):
        results = run_contract(lambda: AWSBedrockFake(world="sim"), self.fake.capabilities())
        failures = [c for c in results if not c.ok]
        self.assertEqual(len(failures), 0, f"Fake contract checks failed: {failures}")

    def test_adapter_contract(self):
        results = run_contract(lambda: AWSBedrockAdapter(world="sim"), self.adapter.capabilities())
        failures = [c for c in results if not c.ok]
        self.assertEqual(len(failures), 0, f"Adapter contract checks failed: {failures}")

    def test_execute_invoke_model_sim(self):
        res = self.adapter.execute(
            "bedrock_invoke_model",
            {"model": "anthropic.claude-3-5-sonnet-20241022-v2:0", "prompt": "Hello world from Bedrock"},
            idem_key="test-bedrock-inv-1",
            idem_class="none",
            dry_run=False,
            deadline=self.deadline,
            provenance=[{"field": "$.input", "source": "test", "trust": "internal"}],
        )
        self.assertTrue(res.ok)
        self.assertIn("Simulated response", res.data.get("output_text", ""))

    def test_dry_run_does_not_mutate_credits(self):
        # Initial check
        status1 = self.adapter.pool.pool_status()
        initial_remaining = status1["total_remaining_usd"]

        res = self.adapter.execute(
            "bedrock_invoke_model",
            {"model": "anthropic.claude-3-5-sonnet-20241022-v2:0", "prompt": "Dry run prompt"},
            idem_key="test-bedrock-dry-1",
            idem_class="none",
            dry_run=True,
            deadline=self.deadline,
            provenance=[{"field": "$.input", "source": "test", "trust": "internal"}],
        )
        self.assertTrue(res.ok)
        self.assertTrue(res.dry_run)
        self.assertIn("predicted_cost_usd", res.data)

        # Confirm credits unchanged
        status2 = self.adapter.pool.pool_status()
        self.assertEqual(status2["total_remaining_usd"], initial_remaining)

    def test_zero_cost_guardrail_fencing(self):
        # Force account below safety buffer
        active = self.adapter.pool.get_active_account()
        self.assertIsNotNone(active)
        active.remaining_usd = 4.50  # Below 5.00 safety buffer
        eligible, reason = self.adapter.pool.check_eligibility(active)
        self.assertFalse(eligible)
        self.assertEqual(active.status, "depleted")
        self.assertIn("safety buffer", reason)


if __name__ == "__main__":
    unittest.main()
