"""Unit tests for FreeLLMAPI Universal Free-Tier Token Pool & Router (scripts/lib/freellm_pool.py)."""

import os
import sys
import unittest
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(1, str(REPO / "scripts"))

from scripts.lib.freellm_pool import (
    FreeLLMProvider,
    PROVIDER_CATALOG,
    KeyVault,
    FreeLLMPoolManager,
    SmartFallbackRouter,
    get_total_free_tier_capacity,
)


class TestFreeLLMPool(unittest.TestCase):
    def test_catalog_coverage_and_capacity(self):
        """Verify catalog contains 34+ free providers and >= 7.0B tokens/month capacity."""
        self.assertGreaterEqual(len(PROVIDER_CATALOG), 34)
        
        # Verify key providers are present
        expected_providers = [
            "google_gemini", "groq", "cerebras", "mistral", "sambanova",
            "together", "deepinfra", "openrouter_free", "huggingface",
            "cloudflare", "github_models", "cohere", "voyage"
        ]
        for p in expected_providers:
            self.assertIn(p, PROVIDER_CATALOG, f"Provider {p} missing from catalog")
            self.assertTrue(PROVIDER_CATALOG[p].base_url)
            self.assertGreater(PROVIDER_CATALOG[p].monthly_token_quota, 0)
            self.assertGreater(len(PROVIDER_CATALOG[p].models), 0)

        total_cap = get_total_free_tier_capacity()
        # ~7.4 Billion tokens
        self.assertGreaterEqual(total_cap, 7_000_000_000)

    def test_key_vault_encryption_and_redaction(self):
        """Test AES-256-GCM encryption, decryption, and secure redaction."""
        secret = "sk-ant-api03-secret-key-1234567890abcdef"
        passphrase = "test-master-passphrase-32bytes!!"
        
        vault = KeyVault(passphrase=passphrase)
        encrypted = vault.encrypt(secret)
        self.assertNotEqual(encrypted, secret)
        self.assertTrue(encrypted.startswith("vault:v1:"))
        
        decrypted = vault.decrypt(encrypted)
        self.assertEqual(decrypted, secret)
        
        # Test redaction
        redacted = vault.redact(secret)
        self.assertTrue(redacted.endswith("cdef"))
        self.assertNotIn("1234567890", redacted)

    def test_key_vault_env_resolution(self):
        """Test resolving keys from environment with template fallback."""
        vault = KeyVault()
        os.environ["TEST_FREE_LLM_KEY"] = "sk-live-env-value"
        try:
            resolved = vault.resolve("${TEST_FREE_LLM_KEY:-default_fallback}")
            self.assertEqual(resolved, "sk-live-env-value")
            
            resolved_fallback = vault.resolve("${NON_EXISTENT_KEY:-my_default}")
            self.assertEqual(resolved_fallback, "my_default")
        finally:
            os.environ.pop("TEST_FREE_LLM_KEY", None)

    def test_pool_manager_rotation_and_cooldown(self):
        """Test multi-key pool rotation and rate-limit cooldown handling."""
        manager = FreeLLMPoolManager(load_disk_keys=False)
        provider = "groq"
        
        manager.add_key(provider, "key-groq-1")
        manager.add_key(provider, "key-groq-2")
        
        # Initial status
        status = manager.get_provider_status(provider)
        self.assertEqual(status["active_keys_count"], 2)
        self.assertEqual(status["cooldown_keys_count"], 0)
        
        # Pick keys (round-robin)
        k1 = manager.acquire_key(provider)
        self.assertEqual(k1, "key-groq-1")
        k2 = manager.acquire_key(provider)
        self.assertEqual(k2, "key-groq-2")
        k3 = manager.acquire_key(provider)
        self.assertEqual(k3, "key-groq-1")
        
        # Trigger 429 rate-limit on key-groq-1
        manager.report_rate_limit(provider, "key-groq-1", cooldown_seconds=2)
        
        status_after_429 = manager.get_provider_status(provider)
        self.assertEqual(status_after_429["active_keys_count"], 1)
        self.assertEqual(status_after_429["cooldown_keys_count"], 1)
        
        # Next acquire MUST return key-groq-2 (since key-groq-1 is cooling down)
        k_next = manager.acquire_key(provider)
        self.assertEqual(k_next, "key-groq-2")
        
        # Wait for cooldown to expire
        time.sleep(2.1)
        manager.sweep_cooldowns()
        
        status_after_recovery = manager.get_provider_status(provider)
        self.assertEqual(status_after_recovery["active_keys_count"], 2)
        self.assertEqual(status_after_recovery["cooldown_keys_count"], 0)

    def test_smart_fallback_router(self):
        """Test fallback ladder selection across task domains."""
        router = SmartFallbackRouter()
        
        coding_ladder = router.get_ladder("coding")
        self.assertGreaterEqual(len(coding_ladder), 3)
        self.assertTrue(any("qwen" in m.lower() or "deepseek" in m.lower() or "codestral" in m.lower() for m in coding_ladder))
        
        fast_ladder = router.get_ladder("fast")
        self.assertGreaterEqual(len(fast_ladder), 2)
        self.assertTrue(any("groq" in m.lower() or "cerebras" in m.lower() or "flash" in m.lower() for m in fast_ladder))
        
        # Next candidate on failure
        next_cand = router.get_next_candidate("coding", failed_candidates=[coding_ladder[0]])
        self.assertEqual(next_cand, coding_ladder[1])


if __name__ == "__main__":
    unittest.main()
