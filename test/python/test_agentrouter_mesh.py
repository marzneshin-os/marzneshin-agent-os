"""Unit tests for Phase 5 (ADR-033: Unified AgentRouter Multi-Harness Model Mesh).
Tests scripts/agentrouter_gateway.py, scripts/agentrouter_sync_cli.py,
scripts/mcp_agentrouter.py, and scripts/quota_doctor.py.
"""

import json
import unittest
from datetime import datetime, timezone

from scripts import agentrouter_gateway, agentrouter_sync_cli, mcp_agentrouter, quota_doctor


class AgentRouterGatewayTests(unittest.TestCase):
    def test_normalize_gateway_path(self):
        cases = {
            "/v1/v1/messages": "/v1/messages",
            "/messages": "/v1/messages",
            "/v1/messages": "/v1/messages",
            "/v1/v1/chat/completions": "/v1/chat/completions",
            "/chat/completions": "/v1/chat/completions",
            "/v1/chat/completions": "/v1/chat/completions",
            "/v1/v1/responses": "/v1/responses",
            "/responses": "/v1/responses",
            "/v1/responses": "/v1/responses",
            "/models": "/v1/models",
            "/v1/models": "/v1/models",
            "/health": "/v1/health",
            "/v1/health": "/v1/health",
            "/custom/path": "/v1/custom/path",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(agentrouter_gateway.normalize_gateway_path(raw), expected)

    def test_build_waf_headers(self):
        openai_headers = agentrouter_gateway.build_waf_headers("openai", "sk-test-key")
        self.assertEqual(openai_headers.get("User-Agent"), "codex_cli_rs/0.80.0")
        self.assertEqual(openai_headers.get("originator"), "codex_cli_rs")
        self.assertEqual(openai_headers.get("Authorization"), "Bearer sk-test-key")

        anthropic_headers = agentrouter_gateway.build_waf_headers("anthropic", "sk-test-key")
        self.assertEqual(anthropic_headers.get("User-Agent"), "claude-cli/1.0.0")
        self.assertEqual(anthropic_headers.get("x-app"), "cli")
        self.assertEqual(anthropic_headers.get("anthropic-version"), "2023-06-01")
        self.assertEqual(anthropic_headers.get("x-api-key"), "sk-test-key")

    def test_scrub_payload_stateless_models(self):
        payload = {
            "model": "gpt-6.1sol",
            "messages": [{"role": "user", "content": "hi"}],
            "previous_response_id": "resp-1234",
            "reasoning_encrypted_content": "enc-blob",
            "encrypted_content": "enc-blob-2",
            "store": True,
            "output_config": {"format": "json"},
            "thinking": {"type": "adaptive", "budget": 1000},
        }
        scrubbed = agentrouter_gateway.scrub_payload(payload)
        self.assertNotIn("previous_response_id", scrubbed)
        self.assertNotIn("reasoning_encrypted_content", scrubbed)
        self.assertNotIn("encrypted_content", scrubbed)
        self.assertNotIn("store", scrubbed)
        self.assertNotIn("output_config", scrubbed)
        self.assertNotIn("thinking", scrubbed)
        self.assertEqual(scrubbed["model"], "gpt-6.1sol")

    def test_scrub_payload_preserves_standard_thinking(self):
        payload = {
            "model": "claude-opus-5",
            "messages": [{"role": "user", "content": "test"}],
            "thinking": {"type": "enabled", "budget_tokens": 2048},
        }
        scrubbed = agentrouter_gateway.scrub_payload(payload)
        self.assertEqual(scrubbed["thinking"], {"type": "enabled", "budget_tokens": 2048})

    def test_sanitize_sse_lines(self):
        lines = [
            "event: message_start\n",
            'data: {"id":"msg_1"}\n',
            "\n",
            "event: billing_summary\n",
            'data: {"tokens":100}\n',
            "\n",
            "data: null\n",
            "\n",
            "event: content_block_delta\n",
            'data: {"delta":{"text":"hello"}}\n',
            "\n",
        ]
        sanitized = agentrouter_gateway.sanitize_sse_lines(lines)
        joined = "".join(sanitized)
        self.assertNotIn("billing_summary", joined)
        self.assertNotIn("data: null", joined)
        self.assertIn("message_start", joined)
        self.assertIn("content_block_delta", joined)

    def test_is_decryption_or_channel_error(self):
        self.assertTrue(agentrouter_gateway.is_decryption_or_channel_error(503, "no available channel"))
        self.assertTrue(agentrouter_gateway.is_decryption_or_channel_error(500, "Decryption Failure in node 2"))
        self.assertTrue(agentrouter_gateway.is_decryption_or_channel_error(200, "跨资源访问 (Cross-Resource Access)"))
        self.assertTrue(agentrouter_gateway.is_decryption_or_channel_error(400, "解密失败"))
        self.assertFalse(agentrouter_gateway.is_decryption_or_channel_error(200, '{"choices":[{"text":"ok"}]}'))

    def test_translate_anthropic_to_openai(self):
        anth_payload = {
            "model": "gpt-6.1sol",
            "system": "You are a helpful assistant.",
            "messages": [
                {"role": "user", "content": "Hello!"},
                {"role": "assistant", "content": [{"type": "text", "text": "Hi there!"}]},
                {"role": "user", "content": [{"type": "text", "text": "Next question"}]},
            ],
            "max_tokens": 2048,
            "stream": True,
        }
        oai_payload = agentrouter_gateway.translate_anthropic_to_openai(anth_payload)
        self.assertEqual(oai_payload["model"], "gpt-6.1sol")
        self.assertEqual(oai_payload["max_tokens"], 2048)
        self.assertTrue(oai_payload["stream"])
        self.assertEqual(oai_payload["messages"][0], {"role": "system", "content": "You are a helpful assistant."})
        self.assertEqual(oai_payload["messages"][1], {"role": "user", "content": "Hello!"})
        self.assertEqual(oai_payload["messages"][2], {"role": "assistant", "content": "Hi there!"})
        self.assertEqual(oai_payload["messages"][3], {"role": "user", "content": "Next question"})

    def test_translate_openai_to_anthropic(self):
        oai_resp = {
            "id": "chatcmpl-987",
            "model": "gpt-6.1sol",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Translated response."},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        anth_resp = agentrouter_gateway.translate_openai_to_anthropic(oai_resp, "gpt-6.1sol")
        self.assertEqual(anth_resp["type"], "message")
        self.assertEqual(anth_resp["role"], "assistant")
        self.assertEqual(anth_resp["model"], "gpt-6.1sol")
        self.assertEqual(anth_resp["content"], [{"type": "text", "text": "Translated response."}])
        self.assertEqual(anth_resp["stop_reason"], "end_turn")
        self.assertEqual(anth_resp["usage"]["input_tokens"], 10)
        self.assertEqual(anth_resp["usage"]["output_tokens"], 20)

    def test_get_failover_chain_during_and_outside_astra_window(self):
        # 07:30 UTC: inside Astra supply window
        window_utc = datetime(2026, 10, 24, 7, 30, tzinfo=timezone.utc)
        chain_window = agentrouter_gateway.get_failover_chain("gpt-6.1sol", utc_now=window_utc)
        self.assertEqual(chain_window[0], "gpt-6.1sol")
        self.assertEqual(chain_window[1], "gpt-6-astra")

        # 12:00 UTC: outside Astra supply window
        normal_utc = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
        chain_normal = agentrouter_gateway.get_failover_chain("gpt-6.1sol", utc_now=normal_utc)
        self.assertEqual(chain_normal[0], "gpt-6.1sol")
        self.assertIn("claude-opus-5", chain_normal)
        self.assertIn("gpt-6-astra", chain_normal)


class AgentRouterSyncCliTests(unittest.TestCase):
    def test_render_all_supported_targets(self):
        for target in agentrouter_sync_cli.HARNESS_TARGETS:
            rendered = agentrouter_sync_cli.render_config(target, use_local_gateway=True)
            self.assertIsInstance(rendered, str)
            self.assertGreater(len(rendered), 10)
            if target == "codex":
                self.assertIn("[model_providers.AgentRouter]", rendered)
                self.assertIn("gpt-6.1sol", rendered)
            elif target == "claude-code":
                self.assertIn("ANTHROPIC_BASE_URL", rendered)
                self.assertIn("claude-opus-5", rendered)
            elif target == "opencode":
                parsed = json.loads(rendered)
                self.assertIn("provider", parsed)
            elif target == "ccr":
                parsed = json.loads(rendered)
                self.assertIn("Router", parsed)

    def test_sync_dry_run(self):
        result = agentrouter_sync_cli.sync_target("codex", dry_run=True, use_local_gateway=True)
        self.assertIsInstance(result, dict)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["status"], "dry_run_passed")


class McpAgentRouterTests(unittest.TestCase):
    def test_execute_tool_status(self):
        res = mcp_agentrouter.execute_tool("agentrouter_status", {})
        self.assertIn("gateway_version", res)
        self.assertIn("local_gateway_url", res)
        self.assertIn("astra_window_active", res)
        self.assertIn("models_count", res)
        self.assertEqual(res["models_count"], 7)

    def test_execute_tool_models(self):
        res = mcp_agentrouter.execute_tool("agentrouter_models", {})
        self.assertIn("models", res)
        self.assertEqual(len(res["models"]), 7)
        ids = list(res["models"].keys())
        self.assertIn("gpt-6.1sol", ids)
        self.assertIn("gpt-6-astra", ids)
        self.assertIn("claude-opus-5", ids)
        self.assertIn("deepseek-v4-flash", ids)

    def test_execute_tool_render_config(self):
        res = mcp_agentrouter.execute_tool("agentrouter_render_config", {"target": "codex"})
        self.assertIn("config", res)
        self.assertIn("gpt-6.1sol", res["config"])

    def test_execute_tool_route_plan(self):
        plan_crit = mcp_agentrouter.execute_tool("agentrouter_route_plan", {"task_complexity": "critical", "utc_hour": 7})
        self.assertEqual(plan_crit["primary_model"], "gpt-6-astra")
        self.assertIn("failover_chain", plan_crit)

        plan_med = mcp_agentrouter.execute_tool("agentrouter_route_plan", {"task_complexity": "medium"})
        self.assertEqual(plan_med["primary_model"], "glm-5.3")

    def test_handle_jsonrpc(self):
        # initialize
        init_req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        init_resp = mcp_agentrouter.handle_jsonrpc(init_req)
        self.assertIn("result", init_resp)
        self.assertEqual(init_resp["result"]["serverInfo"]["name"], "agentrouter-mesh")

        # tools/list
        list_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        list_resp = mcp_agentrouter.handle_jsonrpc(list_req)
        self.assertIn("tools", list_resp["result"])
        self.assertEqual(len(list_resp["result"]["tools"]), 4)

        # tools/call
        call_req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "agentrouter_status", "arguments": {}},
        }
        call_resp = mcp_agentrouter.handle_jsonrpc(call_req)
        self.assertIn("content", call_resp["result"])
        self.assertIn("gateway_version", call_resp["result"]["content"][0]["text"])


class QuotaDoctorAgentRouterTests(unittest.TestCase):
    def test_check_astra_window(self):
        window_active = datetime(2026, 10, 24, 7, 15, tzinfo=timezone.utc)
        res_active = quota_doctor.check_astra_window(window_active)
        self.assertTrue(res_active["window_active"])
        self.assertEqual(res_active["recommended_apex_model"], "gpt-6-astra")

        window_inactive = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
        res_inactive = quota_doctor.check_astra_window(window_inactive)
        self.assertFalse(res_inactive["window_active"])
        self.assertEqual(res_inactive["recommended_apex_model"], "gpt-6.1sol")

    def test_model_tiers_contain_agentrouter_models(self):
        tier_0_models = quota_doctor.MODEL_TIERS["tier_0"]["models"]
        self.assertIn("gpt-6.1sol", tier_0_models)
        self.assertIn("gpt-6-astra", tier_0_models)
        self.assertIn("claude-opus-5", tier_0_models)

        tier_1_models = quota_doctor.MODEL_TIERS["tier_1"]["models"]
        self.assertIn("glm-5.3", tier_1_models)

        tier_2_models = quota_doctor.MODEL_TIERS["tier_2"]["models"]
        self.assertIn("deepseek-v4-flash", tier_2_models)


if __name__ == "__main__":
    unittest.main()
