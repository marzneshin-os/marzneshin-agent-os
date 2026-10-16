"""Unit tests for AWS Bedrock Promotional Credit Pool (scripts/lib/aws_bedrock_credits.py)."""

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
import sim
if str(REPO / "scripts") not in sys.path:
    sys.path.append(str(REPO / "scripts"))

from scripts.lib.aws_bedrock_credits import (
    BedrockAccount,
    BedrockCreditPoolManager,
    BEDROCK_MODEL_PRICING,
    DEFAULT_SAFETY_BUFFER_USD,
)
from scripts.lib import clock


class TestAWSBedrockCredits(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_path = Path(self.temp_dir.name) / "vault.json"
        self.manager = BedrockCreditPoolManager(vault_path=self.vault_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_model_pricing_matrix(self):
        """Verify model pricing rates for key Bedrock models."""
        sonnet = BEDROCK_MODEL_PRICING.get("anthropic.claude-3-5-sonnet-20241022-v2:0")
        self.assertIsNotNone(sonnet)
        self.assertEqual(sonnet.input_price_per_m, 3.00)
        self.assertEqual(sonnet.output_price_per_m, 15.00)

        llama = BEDROCK_MODEL_PRICING.get("meta.llama3-3-70b-instruct-v1:0")
        self.assertIsNotNone(llama)
        self.assertEqual(llama.input_price_per_m, 0.72)

        cost = self.manager.calculate_cost_usd(
            "anthropic.claude-3-5-sonnet-20241022-v2:0",
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
        )
        self.assertEqual(round(cost, 2), 18.00)

    def test_account_registration_and_defaults(self):
        """Verify default credit grant ($100), safety buffer ($5.00), and 6-month expiry."""
        acc = self.manager.register_account(
            account_id="test_acc_1",
            alias="Test Account 1",
            access_key_id="ASIAKEY1",
            secret_access_key="secret1",
            initial_credit_usd=100.0,
        )
        self.assertEqual(acc.account_id, "test_acc_1")
        self.assertEqual(acc.remaining_usd, 100.0)
        self.assertEqual(acc.spent_usd, 0.0)
        self.assertEqual(acc.status, "active")

        # Expiry should be approx 180 days in future
        exp_dt = datetime.fromisoformat(acc.expires_at)
        now_dt = clock.now()
        diff_days = (exp_dt - now_dt).days
        self.assertTrue(175 <= diff_days <= 185)

    def test_zero_cost_safety_buffer_fencing(self):
        """Verify account is retired to 'depleted' before credits reach 0 to prevent billable charges."""
        acc = self.manager.register_account(
            account_id="test_acc_fence",
            alias="Fence Account",
            access_key_id="ASIAKEYFENCE",
            secret_access_key="secretfence",
            initial_credit_usd=100.0,
        )
        # Spend down to $6.00 (above $5.00 buffer) -> should remain eligible
        acc.spent_usd = 94.0
        acc.remaining_usd = 6.0
        eligible, reason = self.manager.check_eligibility(acc)
        self.assertTrue(eligible)

        # Spend down to $4.99 (below $5.00 buffer) -> must FAIL CLOSED
        acc.spent_usd = 95.01
        acc.remaining_usd = 4.99
        eligible, reason = self.manager.check_eligibility(acc)
        self.assertFalse(eligible)
        self.assertEqual(acc.status, "depleted")
        self.assertIn("safety buffer", reason)

    def test_grant_expiration_fencing(self):
        """Verify expired grants are flagged and refused."""
        acc = self.manager.register_account(
            account_id="test_acc_expired",
            alias="Expired Account",
            access_key_id="ASIAEXP",
            secret_access_key="secretexp",
            initial_credit_usd=100.0,
        )
        # Set expiry in the past
        past_dt = clock.now() - timedelta(days=5)
        acc.expires_at = past_dt.isoformat()
        eligible, reason = self.manager.check_eligibility(acc)
        self.assertFalse(eligible)
        self.assertEqual(acc.status, "expired")
        self.assertIn("Grant expired", reason)

    def test_multi_account_rotation(self):
        """Verify automatic rotation selects highest credit balance account."""
        self.manager.register_account(
            account_id="acc_low",
            alias="Low Credit Account",
            access_key_id="K1",
            secret_access_key="S1",
            initial_credit_usd=20.0,
        )
        self.manager.register_account(
            account_id="acc_high",
            alias="High Credit Account",
            access_key_id="K2",
            secret_access_key="S2",
            initial_credit_usd=150.0,
        )
        chosen = self.manager.rotate_account()
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen.account_id, "acc_high")

    def test_onboarding_exploration_tasks(self):
        """Verify completing the 5 tasks unlocks additional credits up to $200."""
        acc = self.manager.register_account(
            account_id="acc_onboard",
            alias="Onboarding Account",
            access_key_id="K3",
            secret_access_key="S3",
            initial_credit_usd=100.0,
        )
        self.assertEqual(acc.initial_credit_usd, 100.0)

        # Complete ec2 task (+20)
        res = self.manager.complete_onboarding_task("acc_onboard", "ec2", resource_cleaned=True)
        self.assertTrue(res["ok"])
        self.assertEqual(acc.initial_credit_usd, 120.0)
        self.assertEqual(acc.remaining_usd, 120.0)

        # Complete rds task (+20)
        self.manager.complete_onboarding_task("acc_onboard", "rds", resource_cleaned=True)
        self.assertEqual(acc.initial_credit_usd, 140.0)

    def test_secret_redaction(self):
        """Verify secret keys are redacted in export / status dictionaries."""
        acc = self.manager.register_account(
            account_id="acc_secret",
            alias="Secret Account",
            access_key_id="AKIA12345678",
            secret_access_key="super_secret_aws_key",
            initial_credit_usd=100.0,
        )
        redacted = acc.to_dict(redact_secret=True)
        self.assertEqual(redacted["secret_access_key"], "[REDACTED]")


if __name__ == "__main__":
    unittest.main()
