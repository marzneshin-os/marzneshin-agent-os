"""Unit tests for TurboFieldfare Adapter (Gemma 4 26B-A4B SSD Streaming Engine)."""

import unittest
from datetime import datetime, timezone, timedelta
from adapters.turbo_fieldfare import TurboFieldfareAdapter, LayerLFUCache


class TestTurboFieldfareAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = TurboFieldfareAdapter(world="sim")
        self.deadline = datetime.now(timezone.utc) + timedelta(seconds=30)

    def test_healthz(self):
        health = self.adapter.healthz()
        self.assertTrue(health.ok)
        self.assertIn("TurboFieldfare", health.detail)

    def test_capabilities(self):
        caps = self.adapter.capabilities()
        self.assertIn("check_environment", caps)
        self.assertIn("get_model_card", caps)
        self.assertIn("chat_completion", caps)
        self.assertIn("stream_expert", caps)
        self.assertIn("repack_status", caps)
        self.assertIn("benchmark_ssd_inference", caps)

    def test_check_environment(self):
        res = self.adapter.execute(
            "check_environment",
            {},
            idem_key="test-check-env",
            deadline=self.deadline,
        )
        self.assertTrue(res.ok)
        self.assertEqual(res.data["ram_budget_target_gb"], 2.0)
        self.assertIn("free_disk_gb", res.data)
        self.assertIn("apple_silicon_native", res.data)

    def test_get_model_card(self):
        res = self.adapter.execute(
            "get_model_card",
            {},
            idem_key="test-model-card",
            deadline=self.deadline,
        )
        self.assertTrue(res.ok)
        self.assertEqual(res.data["name"], "Gemma 4 26B-A4B IT (TurboFieldfare)")
        self.assertEqual(res.data["total_parameters"], "26B")
        self.assertEqual(res.data["active_parameters_per_token"], "3.88B")
        self.assertEqual(res.data["architecture"]["num_layers"], 30)
        self.assertEqual(res.data["architecture"]["num_routed_experts"], 128)
        self.assertEqual(res.data["architecture"]["top_k_routed_experts"], 8)
        self.assertEqual(res.data["architecture"]["sliding_window_layers"], 25)
        self.assertEqual(res.data["architecture"]["full_attention_layers"], 5)
        self.assertEqual(res.data["memory_budget"]["total_working_ram_budget"], "~2.0 GB")
        self.assertEqual(res.data["pricing"]["input_cost_per_m"], 0.0)

    def test_stream_expert(self):
        top8 = [3, 7, 15, 29, 42, 77, 88, 101]
        res = self.adapter.execute(
            "stream_expert",
            {"layer_idx": 0, "top8_experts": top8},
            idem_key="test-stream-1",
            deadline=self.deadline,
        )
        self.assertTrue(res.ok)
        self.assertEqual(res.data["requested_experts"], top8)
        self.assertEqual(res.data["hits"], 0)
        self.assertEqual(len(res.data["misses"]), 8)
        self.assertEqual(res.data["bytes_read"], 8 * self.adapter.EXPERT_BLOB_SIZE_BYTES)

        # Access same experts again -> should be 100% cache hits
        res2 = self.adapter.execute(
            "stream_expert",
            {"layer_idx": 0, "top8_experts": top8},
            idem_key="test-stream-2",
            deadline=self.deadline,
        )
        self.assertTrue(res2.ok)
        self.assertEqual(res2.data["hits"], 8)
        self.assertEqual(len(res2.data["misses"]), 0)
        self.assertEqual(res2.data["bytes_read"], 0)
        self.assertEqual(res2.data["hit_ratio"], 1.0)

    def test_lfu_cache_eviction(self):
        cache = LayerLFUCache(slot_count=4)
        # Fill slots 0..3 with experts 1, 2, 3, 4
        res1 = cache.access([1, 2, 3, 4])
        self.assertEqual(res1["hits"], 0)

        # Access 1 and 2 multiple times so their frequency rises
        cache.access([1, 2])
        cache.access([1, 2])

        # Access new expert 5 -> should evict 3 or 4 (use_count = 1)
        res2 = cache.access([5])
        self.assertEqual(res2["misses"], [5])

        # Expert 1 and 2 should still be in cache
        res3 = cache.access([1, 2])
        self.assertEqual(res3["hits"], 2)

    def test_benchmark_ssd_inference(self):
        res = self.adapter.execute(
            "benchmark_ssd_inference",
            {"iterations": 2},
            idem_key="test-bench",
            deadline=self.deadline,
        )
        self.assertTrue(res.ok)
        self.assertIn("read_speed_mb_s", res.data)
        self.assertIn("projected_tok_per_sec", res.data)
        self.assertEqual(res.data["status"], "PASS")

    def test_chat_completion_sim(self):
        res = self.adapter.execute(
            "chat_completion",
            {"prompt": "Explain Gemma 4 MoE routing"},
            idem_key="test-chat",
            dry_run=True,
            deadline=self.deadline,
        )
        self.assertTrue(res.ok)
        self.assertEqual(res.data["model"], "gemma-4-26b-a4b-it")
        self.assertEqual(res.data["cost_usd"], 0.0)
        self.assertIn("Simulation", res.data["content"])

    def test_repack_status(self):
        res = self.adapter.execute(
            "repack_status",
            {"path": "non_existent_model_dir"},
            idem_key="test-repack",
            deadline=self.deadline,
        )
        self.assertTrue(res.ok)
        self.assertFalse(res.data["exists"])
        self.assertEqual(res.data["status"], "not_installed")

    def test_idempotency_replay(self):
        res1 = self.adapter.execute(
            "get_model_card",
            {},
            idem_key="repeatable-key-tf",
            deadline=self.deadline,
        )
        self.assertTrue(res1.ok)
        self.assertFalse(res1.replayed)

        res2 = self.adapter.execute(
            "get_model_card",
            {},
            idem_key="repeatable-key-tf",
            deadline=self.deadline,
        )
        self.assertTrue(res2.ok)
        self.assertTrue(res2.replayed)

    def test_invalid_operation(self):
        res = self.adapter.execute("invalid_op", {})
        self.assertFalse(res.ok)
        self.assertIn("Unknown operation", res.error)


if __name__ == "__main__":
    unittest.main()
