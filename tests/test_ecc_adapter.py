"""Unit tests and contract tests for EccAdapter (adapters/ecc.py)."""

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
from adapters.ecc import EccAdapter
from sim.fakes.ecc import EccFake


class TestEccAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = EccAdapter(world="sim")
        self.fake = EccFake(world="sim")
        self.deadline = datetime.now(timezone.utc) + timedelta(seconds=30)

    def test_healthz(self):
        h = self.adapter.healthz()
        self.assertTrue(h.ok)
        self.assertIn("ecc", h.detail.lower())

    def test_capabilities(self):
        caps = self.adapter.capabilities()
        self.assertIn("agentshield_scan", caps)
        self.assertIn("instinct_learn", caps)
        self.assertIn("instinct_query", caps)
        self.assertIn("instinct_update_confidence", caps)
        self.assertIn("harness_audit", caps)
        self.assertIn("harness_sync_rules", caps)

    def test_fake_contract(self):
        results = run_contract(lambda: EccFake(world="sim"), self.fake.capabilities())
        failures = [c for c in results if not c.ok]
        self.assertEqual(len(failures), 0, f"Fake contract checks failed: {failures}")

    def test_adapter_contract(self):
        results = run_contract(lambda: EccAdapter(world="sim"), self.adapter.capabilities())
        failures = [c for c in results if not c.ok]
        self.assertEqual(len(failures), 0, f"Adapter contract checks failed: {failures}")

    def test_execute_scan_sim(self):
        res = self.adapter.execute(
            "agentshield_scan",
            {},
            idem_key="test-scan-1",
            idem_class="none",
            dry_run=False,
            deadline=self.deadline,
            provenance=[{"field": "$.input", "source": "test", "trust": "internal"}],
        )
        self.assertTrue(res.ok)
        self.assertTrue(res.data.get("passed"))

    def test_execute_instinct_query_sim(self):
        res = self.adapter.execute(
            "instinct_query",
            {"domain": "general"},
            idem_key="test-query-1",
            idem_class="none",
            dry_run=False,
            deadline=self.deadline,
            provenance=[{"field": "$.input", "source": "test", "trust": "internal"}],
        )
        self.assertTrue(res.ok)
        self.assertGreaterEqual(res.data.get("count", 0), 1)


if __name__ == "__main__":
    unittest.main()
