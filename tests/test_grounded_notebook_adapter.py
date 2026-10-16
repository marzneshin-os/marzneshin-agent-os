"""Contract and integration tests for GroundedNotebookAdapter & GroundedNotebookFake.

Verifies BUILD-SPEC §4 Adapter Contract (C1 through C9) and ADR-026.
"""

import shutil
import sys
import tempfile
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
from adapters.grounded_notebook import GroundedNotebookAdapter
from sim.fakes.grounded_notebook import GroundedNotebookFake


class TestGroundedNotebookAdapter(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="test_nb_adapter_"))
        self.adapter = GroundedNotebookAdapter(world="sim", root_dir=self.tmp_dir)
        self.fake = GroundedNotebookFake(world="sim")
        self.deadline = datetime.now(timezone.utc) + timedelta(seconds=30)
        self.prov = [{"field": "$.input", "source": "test", "trust": "internal"}]

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_healthz(self):
        h = self.adapter.healthz()
        self.assertTrue(h.ok)
        self.assertIn("grounded notebook", h.detail.lower())

        hf = self.fake.healthz()
        self.assertTrue(hf.ok)

    def test_capabilities(self):
        caps = self.adapter.capabilities()
        for expected in [
            "create_notebook",
            "ingest_sources",
            "grounded_query",
            "synthesize_sources",
            "verify_grounding",
            "list_notebooks",
            "get_notebook",
        ]:
            self.assertIn(expected, caps)

    def test_fake_contract(self):
        results = run_contract(lambda: GroundedNotebookFake(world="sim"), self.fake.capabilities())
        failures = [c for c in results if not c.ok]
        self.assertEqual(len(failures), 0, f"Fake contract checks failed: {failures}")

    def test_adapter_contract(self):
        results = run_contract(
            lambda: GroundedNotebookAdapter(world="sim", root_dir=self.tmp_dir),
            self.adapter.capabilities(),
        )
        failures = [c for c in results if not c.ok]
        self.assertEqual(len(failures), 0, f"Adapter contract checks failed: {failures}")

    def test_end_to_end_grounding_flow(self):
        # 1. Create notebook
        res_create = self.adapter.execute(
            "create_notebook",
            {"notebook_id": "nb-e2e", "title": "End-to-End Spec", "description": "E2E testing"},
            idem_key="e2e:create:1",
            deadline=self.deadline,
            provenance=self.prov,
        )
        self.assertTrue(res_create.ok)
        self.assertEqual(res_create.data["notebook_id"], "nb-e2e")

        # 2. Ingest source
        res_ingest = self.adapter.execute(
            "ingest_sources",
            {
                "notebook_id": "nb-e2e",
                "source_name": "build_spec_v2.md",
                "content": """# Section 16: Verification & Simulation
All simulation scenarios must run under 60 seconds.
Two-key verification requires QA Gate and Adversarial Review.
""",
            },
            idem_key="e2e:ingest:1",
            deadline=self.deadline,
            provenance=self.prov,
        )
        self.assertTrue(res_ingest.ok)

        # 3. Grounded query
        res_query = self.adapter.execute(
            "grounded_query",
            {"notebook_id": "nb-e2e", "query": "two-key verification adversarial review", "top_k": 2},
            idem_key="e2e:query:1",
            deadline=self.deadline,
            provenance=self.prov,
        )
        self.assertTrue(res_query.ok)
        self.assertGreater(res_query.data["total_chunks_matched"], 0)
        self.assertIn("build_spec_v2.md", res_query.data["citations"][0]["citation"])

        # 4. Verify grounding (Supported statement)
        res_verif = self.adapter.execute(
            "verify_grounding",
            {
                "notebook_id": "nb-e2e",
                "statement": "Two-key verification requires QA Gate and Adversarial Review.",
            },
            idem_key="e2e:verif:1",
            deadline=self.deadline,
            provenance=self.prov,
        )
        self.assertTrue(res_verif.ok)
        self.assertTrue(res_verif.data["supported"])

        # 5. Verify grounding (Unsupported statement)
        res_unsupported = self.adapter.execute(
            "verify_grounding",
            {
                "notebook_id": "nb-e2e",
                "statement": "The project operates an Ethereum smart contract validator.",
            },
            idem_key="e2e:unsupported:1",
            deadline=self.deadline,
            provenance=self.prov,
        )
        self.assertTrue(res_unsupported.ok)
        self.assertFalse(res_unsupported.data["supported"])


if __name__ == "__main__":
    unittest.main()
