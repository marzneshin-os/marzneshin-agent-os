#!/usr/bin/env python3
"""Tests for the OmniRoute and Claude Code Router (CCR) Gateway integration."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

from lib import tokensaver, router
from adapters.omniroute import OmniRouteAdapter, CCRAdapter, _build_url


class TestTokenSaver(unittest.TestCase):
    def test_apply_token_saver_rtk(self):
        body = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "tool", "content": "Line\n" * 300}
            ]
        }
        metrics = tokensaver.apply_token_saver(body, rtk_enabled=True, ponytail_enabled=False)
        self.assertIsNotNone(metrics.rtk_filter)
        self.assertFalse(metrics.ponytail_applied)
        self.assertIsNone(metrics.caveman_level)

    def test_apply_token_saver_caveman(self):
        body = {
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "Can you please explain this?"}
            ]
        }
        metrics = tokensaver.apply_token_saver(body, rtk_enabled=False, caveman_level="full")
        self.assertIsNotNone(metrics.caveman_level)
        self.assertEqual(body["messages"][0]["role"], "system")
        self.assertTrue("caveman" in body["messages"][0]["content"].lower())

    def test_apply_token_saver_ponytail(self):
        body = {
            "model": "gpt-4o",
            "messages": [
                {"role": "user", "content": "Explain python dicts"}
            ]
        }
        metrics = tokensaver.apply_token_saver(body, rtk_enabled=False, ponytail_enabled=True)
        self.assertTrue(metrics.ponytail_applied)
        self.assertEqual(body["messages"][0]["role"], "system")
        self.assertTrue("Answer only" in body["messages"][0]["content"])


class TestRouter(unittest.TestCase):
    def test_load_config(self):
        config = router.load_config()
        self.assertIn("gateways", config)
        self.assertIn("combos", config)
        self.assertIn("quota", config)
        self.assertIn("ccr", config["gateways"])

    def test_expand_env_vars(self):
        raw = {
            "key1": "${TEST_VAR_ROUTER:-default_val}",
            "key2": "${TEST_UNSET_VAR}",
            "nested": ["${TEST_VAR_ROUTER:-fallback}"]
        }
        expanded = router.expand_env_vars(raw)
        self.assertEqual(expanded["key1"], "default_val")
        self.assertEqual(expanded["key2"], "")
        self.assertEqual(expanded["nested"][0], "fallback")

        # Test with environment set
        os.environ["TEST_VAR_ROUTER"] = "custom_val"
        try:
            expanded2 = router.expand_env_vars(raw)
            self.assertEqual(expanded2["key1"], "custom_val")
            self.assertEqual(expanded2["nested"][0], "custom_val")
        finally:
            del os.environ["TEST_VAR_ROUTER"]

    def test_classify_error(self):
        self.assertEqual(router.classify_error(429, "Too Many Requests"), "rate_limited")
        self.assertEqual(router.classify_error(429, "quota exhausted"), "quota_exhausted")
        self.assertEqual(router.classify_error(401, "Unauthorized"), "auth_failed")
        self.assertEqual(router.classify_error(500, "Internal Error"), "provider_error")

    def test_combo_resolution(self):
        combo = router.get_combo_strategy("fable-planner")
        self.assertIsNotNone(combo)
        self.assertEqual(combo.strategy, "fallback")
        self.assertTrue(len(combo.members) > 0)
        # Verify CCR members are preserved
        ccr_members = [m for m in combo.members if m.startswith("ccr:")]
        self.assertTrue(len(ccr_members) > 0)

    def test_build_url(self):
        # Prevents double /v1/v1/
        self.assertEqual(
            _build_url("http://127.0.0.1:3456/v1", "v1/models"),
            "http://127.0.0.1:3456/v1/models"
        )
        self.assertEqual(
            _build_url("http://localhost:3000", "v1/chat/completions"),
            "http://localhost:3000/v1/chat/completions"
        )
        self.assertEqual(
            _build_url("http://127.0.0.1:3456/v1/", "/v1/chat/completions"),
            "http://127.0.0.1:3456/v1/chat/completions"
        )

    def test_ccr_adapter(self):
        adapter = CCRAdapter()
        self.assertEqual(adapter.name, "ccr")
        self.assertEqual(adapter.gateway_name, "ccr")
        config = router.load_config()
        gw_name, gw_cfg = adapter._resolve_gateway(config)
        self.assertEqual(gw_name, "ccr")
        self.assertTrue(gw_cfg.get("enabled", False))

    def test_adapter_capabilities(self):
        adapter = OmniRouteAdapter()
        caps = adapter.capabilities()
        self.assertIn("llm_chat", caps)
        self.assertIn("llm_reason", caps)
        self.assertIn("llm_think", caps)
        self.assertIn("llm_search", caps)

    def test_classify_error_402(self):
        self.assertEqual(router.classify_error(402, "Insufficient credits. Please top up."), "quota_exhausted")

    def test_new_combos(self):
        for combo_name in ("antigravity", "fable-reasoning", "thinking-deep", "free-mega"):
            combo = router.get_combo_strategy(combo_name)
            self.assertIsNotNone(combo, f"Combo {combo_name} should exist")
            self.assertTrue(len(combo.members) > 0)
            # Verify xkiro or freemodels presence
            has_new_gw = any(m.startswith("xkiro:") or m.startswith("freemodels:") for m in combo.members)
            self.assertTrue(has_new_gw, f"Combo {combo_name} should contain new gateways")


if __name__ == "__main__":
    unittest.main(verbosity=2)
