"""Unit tests and contract tests for FreeLLMAdapter (adapters/freellm.py)."""

import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
import sim
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(1, str(REPO / "scripts"))

from adapters.contract import run_contract
from adapters.freellm import FreeLLMAdapter
from sim.fakes.freellm import FreeLLMFake


class TestFreeLLMAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = FreeLLMAdapter(world="sim")
        self.fake = FreeLLMFake(world="sim")
        self.deadline = datetime.now(timezone.utc) + timedelta(seconds=30)

    def test_healthz(self):
        h = self.adapter.healthz()
        self.assertTrue(h.ok)
        self.assertIn("freellm", h.detail.lower())

    def test_capabilities(self):
        caps = self.adapter.capabilities()
        self.assertIn("llm_chat", caps)
        self.assertIn("llm_messages", caps)
        self.assertIn("pool_status", caps)
        self.assertIn("rotate_key", caps)
        self.assertIn("test_provider", caps)

    def test_fake_contract(self):
        results = run_contract(lambda: FreeLLMFake(world="sim"), self.fake.capabilities())
        failures = [c for c in results if not c.ok]
        self.assertEqual(len(failures), 0, f"Fake contract checks failed: {failures}")

    def test_adapter_contract(self):
        results = run_contract(lambda: FreeLLMAdapter(world="sim"), self.adapter.capabilities())
        failures = [c for c in results if not c.ok]
        self.assertEqual(len(failures), 0, f"Adapter contract checks failed: {failures}")

    def test_execute_pool_status_sim(self):
        res = self.adapter.execute(
            "pool_status",
            {},
            idem_key="test-pool-1",
            idem_class="none",
            dry_run=False,
            deadline=self.deadline,
            provenance=[{"field": "$.input", "source": "test", "trust": "internal"}],
        )
        self.assertTrue(res.ok)
        self.assertGreaterEqual(res.data.get("total_providers", 0), 34)

    def test_execute_rotate_key_sim(self):
        res = self.adapter.execute(
            "rotate_key",
            {"provider": "groq"},
            idem_key="test-rotate-1",
            idem_class="none",
            dry_run=False,
            deadline=self.deadline,
            provenance=[{"field": "$.input", "source": "test", "trust": "internal"}],
        )
        self.assertTrue(res.ok)
        self.assertEqual(res.data.get("provider"), "groq")

    def test_execute_llm_messages_sim(self):
        res = self.adapter.execute(
            "llm_messages",
            {"model": "claude-sonnet-5-free", "messages": [{"role": "user", "content": "hello"}]},
            idem_key="test-msg-1",
            idem_class="none",
            dry_run=False,
            deadline=self.deadline,
            provenance=[{"field": "$.input", "source": "test", "trust": "internal"}],
        )
        self.assertTrue(res.ok)
        self.assertEqual(res.data.get("type"), "message")


if __name__ == "__main__":
    unittest.main()
