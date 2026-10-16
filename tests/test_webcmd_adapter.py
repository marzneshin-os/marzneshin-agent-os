"""Unit tests and contract tests for WebCmdAdapter (adapters/webcmd.py)."""

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
from adapters.webcmd import WebCmdAdapter
from sim.fakes.webcmd import WebCmdFake


class TestWebCmdAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = WebCmdAdapter(world="sim")
        self.fake = WebCmdFake(world="sim")
        self.deadline = datetime.now(timezone.utc) + timedelta(seconds=30)

    def test_healthz(self):
        h = self.adapter.healthz()
        self.assertTrue(h.ok)
        self.assertIn("webcmd", h.detail.lower())

    def test_capabilities(self):
        caps = self.adapter.capabilities()
        self.assertIn("web_browse", caps)
        self.assertIn("web_extract", caps)
        self.assertIn("web_sitemap_get", caps)
        self.assertIn("web_learn_route", caps)
        self.assertIn("web_purge_cache", caps)
        self.assertIn("web_profile_manage", caps)

    def test_fake_contract(self):
        results = run_contract(lambda: WebCmdFake(world="sim"), self.fake.capabilities())
        failures = [c for c in results if not c.ok]
        self.assertEqual(len(failures), 0, f"Fake contract checks failed: {failures}")

    def test_adapter_contract(self):
        results = run_contract(lambda: WebCmdAdapter(world="sim"), self.adapter.capabilities())
        failures = [c for c in results if not c.ok]
        self.assertEqual(len(failures), 0, f"Adapter contract checks failed: {failures}")

    def test_execute_browse_sim(self):
        res = self.adapter.execute(
            "web_browse",
            {"url": "https://example.com/docs"},
            idem_key="test-browse-1",
            idem_class="none",
            dry_run=False,
            deadline=self.deadline,
            provenance=[{"field": "$.input", "source": "test", "trust": "internal"}],
        )
        self.assertTrue(res.ok)
        self.assertIn("compressed_text", res.data)
        self.assertGreater(res.data.get("savings_ratio", 0.0), 0.0)

    def test_execute_sitemap_sim(self):
        res = self.adapter.execute(
            "web_sitemap_get",
            {"domain": "example.com"},
            idem_key="test-sitemap-1",
            idem_class="none",
            dry_run=False,
            deadline=self.deadline,
            provenance=[{"field": "$.input", "source": "test", "trust": "internal"}],
        )
        self.assertTrue(res.ok)


if __name__ == "__main__":
    unittest.main()
