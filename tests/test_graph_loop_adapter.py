import sys
import unittest
from datetime import timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
import sim
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(1, str(REPO / "scripts"))

from scripts.lib import clock
from adapters.contract import run_contract
from adapters.graph_loop import GraphLoopAdapter
from sim.fakes.graph_loop import GraphLoopFake


class TestGraphLoopAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = GraphLoopAdapter(world="sim")
        self.fake = GraphLoopFake(world="sim")
        self.deadline = clock.now() + timedelta(seconds=30)
        self.provenance = [{"field": "$.test", "source": "test", "trust": "internal"}]

    def test_healthz(self):
        h = self.adapter.healthz()
        self.assertTrue(h.ok)
        self.assertIn("graph", h.detail.lower())

    def test_capabilities(self):
        caps = self.adapter.capabilities()
        self.assertIn("run_pipeline", caps)
        self.assertIn("evaluate_gate", caps)
        self.assertIn("execute_code_transform", caps)
        self.assertIn("get_learned_constraints", caps)

    def test_fake_contract(self):
        self.assertEqual(self.fake.capabilities(), self.adapter.capabilities())
        res = self.fake.execute(
            "get_learned_constraints",
            {},
            idem_key="test-fake-1",
            idem_class="scoped",
            dry_run=False,
            deadline=self.deadline,
            provenance=self.provenance
        )
        self.assertTrue(res.ok)
        self.assertGreaterEqual(res.data["count"], 1)

    def test_adapter_operations(self):
        # 1. get_learned_constraints
        res_lc = self.adapter.execute(
            "get_learned_constraints",
            {},
            idem_key="test-lc-1",
            idem_class="scoped",
            dry_run=False,
            deadline=self.deadline,
            provenance=self.provenance
        )
        self.assertTrue(res_lc.ok)
        self.assertGreaterEqual(res_lc.data["count"], 1)

        # 2. execute_code_transform (deduplicate)
        items = [{"id": 1, "val": "x"}, {"id": 1, "val": "dup"}, {"id": 2, "val": "y"}]
        res_ct = self.adapter.execute(
            "execute_code_transform",
            {"operation": "deduplicate", "payload": {"items": items, "key": "id"}},
            idem_key="test-ct-1",
            idem_class="scoped",
            dry_run=False,
            deadline=self.deadline,
            provenance=self.provenance
        )
        self.assertTrue(res_ct.ok)
        self.assertEqual(res_ct.data["task_result"]["verdict"], "GREEN")

        # 3. evaluate_gate (Lane 1 Contained Green)
        t_res = {
            "task_id": "T-TEST",
            "blast_radius": "contained",
            "status": "SUCCESS",
            "tests_passed": True,
            "test_output": "All checks green",
            "summary": "Fix applied"
        }
        res_gate = self.adapter.execute(
            "evaluate_gate",
            {"task_result": t_res},
            idem_key="test-gate-1",
            idem_class="scoped",
            dry_run=False,
            deadline=self.deadline,
            provenance=self.provenance
        )
        self.assertTrue(res_gate.ok)
        self.assertEqual(res_gate.data["verdict"], "GREEN")

        # 4. run_pipeline (Dry Run)
        res_pipe = self.adapter.execute(
            "run_pipeline",
            {"objective": "Verify dry run"},
            idem_key="test-pipe-dry",
            idem_class="none",
            dry_run=True,
            deadline=self.deadline,
            provenance=self.provenance
        )
        self.assertTrue(res_pipe.ok)
        self.assertTrue(res_pipe.data["dry_run"])


if __name__ == "__main__":
    unittest.main()
