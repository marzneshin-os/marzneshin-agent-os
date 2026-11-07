#!/usr/bin/env python3
"""tests/test_prefix_cache.py
Verification suite for Prompt Prefix Stratification and KV-Cache Adapter (ADR-030).
"""

from __future__ import annotations

import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.lib.prefix_cache import (
    CACHE_BREAKPOINT_MARKER,
    PrefixEnvelope,
    canonical_json,
    extract_cache_telemetry,
    strip_volatile_fields,
)


class TestPrefixCache(unittest.TestCase):
    def test_canonical_json_determinism(self):
        d1 = {"z": 1, "a": {"b": 2, "a": 1}}
        d2 = {"a": {"a": 1, "b": 2}, "z": 1}
        self.assertEqual(canonical_json(d1), canonical_json(d2))
        self.assertEqual(canonical_json(d1), '{"a":{"a":1,"b":2},"z":1}')

    def test_strip_volatile_fields(self):
        payload = {
            "name": "agent-orchestrator",
            "timestamp": "2026-11-07T00:00:00Z",
            "nested": {
                "id": "123",
                "updated_at": "2026-11-07T00:01:00Z",
            },
        }
        static_part, volatile_part = strip_volatile_fields(payload)
        self.assertNotIn("timestamp", static_part)
        self.assertNotIn("updated_at", static_part["nested"])
        self.assertEqual(static_part["name"], "agent-orchestrator")
        self.assertEqual(static_part["nested"]["id"], "123")
        self.assertEqual(volatile_part["timestamp"], "2026-11-07T00:00:00Z")
        self.assertEqual(volatile_part["nested"]["updated_at"], "2026-11-07T00:01:00Z")

    def test_prefix_envelope_hash_stability(self):
        env1 = PrefixEnvelope(
            tier0_os_kernel="Kernel V1",
            tier1_agent_persona="Persona V1",
            tier2_session_snapshot="ADR V1",
            tier3_dynamic_tail="Dynamic Tail Run 1",
        )
        env2 = PrefixEnvelope(
            tier0_os_kernel="Kernel V1",
            tier1_agent_persona="Persona V1",
            tier2_session_snapshot="ADR V1",
            tier3_dynamic_tail="Dynamic Tail Run 2 (Mutated State)",
        )
        # Even though dynamic tail changed, static prefix hash must remain byte-identical
        self.assertEqual(env1.prefix_sha256, env2.prefix_sha256)
        self.assertEqual(env1.static_prefix, env2.static_prefix)

    def test_render_markdown_has_breakpoint(self):
        env = PrefixEnvelope(
            tier0_os_kernel="Tier 0",
            tier1_agent_persona="Tier 1",
            tier2_session_snapshot="Tier 2",
            tier3_dynamic_tail="Tier 3",
        )
        rendered = env.render_markdown()
        self.assertIn(CACHE_BREAKPOINT_MARKER, rendered)
        parts = rendered.split(CACHE_BREAKPOINT_MARKER)
        self.assertEqual(len(parts), 2)
        self.assertIn("Tier 0", parts[0])
        self.assertIn("Tier 3", parts[1])

    def test_to_anthropic_messages(self):
        env = PrefixEnvelope(
            tier0_os_kernel="Tier 0",
            tier1_agent_persona="Tier 1",
            tier2_session_snapshot="Tier 2",
            tier3_dynamic_tail="Tier 3",
        )
        payload = env.to_anthropic_messages("What is the next task?")
        system_blocks = payload["system"]
        self.assertEqual(len(system_blocks), 2)
        # Last static block must have ephemeral cache_control
        self.assertEqual(system_blocks[1]["cache_control"], {"type": "ephemeral"})
        self.assertIn("What is the next task?", payload["messages"][0]["content"])

    def test_to_openai_or_vllm_messages(self):
        env = PrefixEnvelope(
            tier0_os_kernel="Tier 0",
            tier1_agent_persona="Tier 1",
            tier2_session_snapshot="Tier 2",
            tier3_dynamic_tail="Tier 3",
        )
        payload = env.to_openai_or_vllm_messages("Execute plan")
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(payload["messages"][0]["content"], env.static_prefix)
        self.assertIn("Execute plan", payload["messages"][1]["content"])

    def test_extract_cache_telemetry(self):
        # OpenAI style
        resp_usage_openai = {
            "prompt_tokens": 1000,
            "completion_tokens": 50,
            "prompt_tokens_details": {"cached_tokens": 900},
            "input_tokens_details": {"cached_tokens": 900},
        }
        res = extract_cache_telemetry("openai", resp_usage_openai)
        self.assertEqual(res["total_input_tokens"], 1000)
        self.assertEqual(res["cached_input_tokens"], 900)
        self.assertEqual(res["uncached_input_tokens"], 100)
        self.assertEqual(res["prefix_cache_hit_ratio"], 0.9)


if __name__ == "__main__":
    unittest.main()

