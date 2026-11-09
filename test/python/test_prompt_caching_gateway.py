"""Unit tests for Prompt Caching integration in AgentRouter Gateway (ADR-034).
Tests cache telemetry mapping, cache_prompt forwarding, and health endpoint metrics.
"""

import json
import unittest

from scripts import agentrouter_gateway


class PromptCachingGatewayTests(unittest.TestCase):
    def setUp(self):
        # Reset global metrics for isolated test runs
        agentrouter_gateway.GATEWAY_CACHE_STATS["total_requests"] = 0
        agentrouter_gateway.GATEWAY_CACHE_STATS["cache_hits"] = 0
        agentrouter_gateway.GATEWAY_CACHE_STATS["cached_tokens"] = 0
        agentrouter_gateway.GATEWAY_CACHE_STATS["prompt_tokens"] = 0

    def test_record_cache_usage_tracks_cumulative_hits_and_tokens(self):
        agentrouter_gateway.record_cache_usage(cached_tokens=0, prompt_tokens=100)
        agentrouter_gateway.record_cache_usage(cached_tokens=800, prompt_tokens=200)

        stats = agentrouter_gateway.GATEWAY_CACHE_STATS
        self.assertEqual(stats["total_requests"], 2)
        self.assertEqual(stats["cache_hits"], 1)
        self.assertEqual(stats["cached_tokens"], 800)
        self.assertEqual(stats["prompt_tokens"], 300)

    def test_translate_openai_to_anthropic_maps_cached_tokens(self):
        oai_response = {
            "id": "chatcmpl-test1234",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Fast cached response"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 1024,
                "completion_tokens": 42,
                "total_tokens": 1066,
                "prompt_tokens_details": {
                    "cached_tokens": 896,
                },
                "cache_creation_input_tokens": 128,
            },
        }

        anth_resp = agentrouter_gateway.translate_openai_to_anthropic(oai_response, "gpt-6.1sol")

        self.assertEqual(anth_resp["role"], "assistant")
        self.assertEqual(anth_resp["content"][0]["text"], "Fast cached response")
        self.assertEqual(anth_resp["usage"]["input_tokens"], 1024)
        self.assertEqual(anth_resp["usage"]["output_tokens"], 42)
        self.assertEqual(anth_resp["usage"]["cache_read_input_tokens"], 896)
        self.assertEqual(anth_resp["usage"]["cache_creation_input_tokens"], 128)

        # Confirm global telemetry was recorded
        stats = agentrouter_gateway.GATEWAY_CACHE_STATS
        self.assertEqual(stats["cache_hits"], 1)
        self.assertEqual(stats["cached_tokens"], 896)

    def test_translate_openai_to_anthropic_parses_llama_cpp_timings(self):
        llama_response = {
            "id": "chatcmpl-llama-999",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "llama.cpp warm cache reply"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
            },
            "timings": {
                "prompt_n": 10,
                "cache_n": 7992,
            },
        }

        anth_resp = agentrouter_gateway.translate_openai_to_anthropic(llama_response, "qwen2.5-coder")
        self.assertEqual(anth_resp["usage"]["cache_read_input_tokens"], 7992)
        self.assertEqual(agentrouter_gateway.GATEWAY_CACHE_STATS["cached_tokens"], 7992)

    def test_translate_anthropic_to_openai_preserves_cache_prompt(self):
        anth_payload = {
            "model": "claude-opus-5",
            "messages": [{"role": "user", "content": "solve this task"}],
            "system": [
                {"type": "text", "text": "Base instructions."},
                {"type": "text", "text": "Detailed rules.", "cache_control": {"type": "ephemeral"}},
            ],
            "cache_prompt": True,
            "max_tokens": 2048,
        }

        oai_payload = agentrouter_gateway.translate_anthropic_to_openai(anth_payload)
        self.assertTrue(oai_payload.get("cache_prompt"))
        self.assertEqual(oai_payload["model"], "claude-opus-5")
        self.assertEqual(len(oai_payload["messages"]), 2)
        self.assertEqual(oai_payload["messages"][0]["role"], "system")
        self.assertIn("Base instructions.", oai_payload["messages"][0]["content"])
        self.assertIn("Detailed rules.", oai_payload["messages"][0]["content"])

    def test_normalize_gateway_path_handles_metrics(self):
        self.assertEqual(agentrouter_gateway.normalize_gateway_path("/metrics"), "/v1/metrics")
        self.assertEqual(agentrouter_gateway.normalize_gateway_path("/v1/metrics"), "/v1/metrics")


if __name__ == "__main__":
    unittest.main()
