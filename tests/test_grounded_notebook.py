"""Unit tests for Grounded Notebook Knowledge Engine (scripts/lib/grounded_notebook.py)."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(1, str(REPO / "scripts"))

from scripts.lib.grounded_notebook import (
    CitationAnchor,
    GroundedNotebook,
    GroundedQueryResult,
    GroundingVerification,
    NotebookStore,
    SourceChunk,
    SourceDocument,
    SourceSynthesis,
)


class TestGroundedNotebookCore(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="test_nb_"))
        self.store = NotebookStore(root_dir=self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_notebook_initialization(self):
        nb = GroundedNotebook(
            notebook_id="nb-spec-01",
            title="Marzneshin Build Spec",
            description="Testing specification notebook",
        )
        self.assertEqual(nb.notebook_id, "nb-spec-01")
        self.assertEqual(nb.title, "Marzneshin Build Spec")
        self.assertEqual(len(nb.sources), 0)
        self.assertEqual(len(nb.chunks), 0)

    def test_ingest_text_and_chunking(self):
        nb = GroundedNotebook("nb-test-chunk", "Chunk Test")
        text_sample = "\n".join([f"Line {i}: Invariant definition for system safety." for i in range(1, 101)])
        doc = nb.ingest_text(text_sample, source_name="spec_v2.md", max_chunk_lines=20, overlap_lines=5)

        self.assertEqual(doc.source_name, "spec_v2.md")
        self.assertEqual(doc.total_lines, 100)
        self.assertGreater(doc.total_chunks, 1)
        self.assertEqual(len(nb.chunks), doc.total_chunks)

        # Check line number preservation and 1-indexing
        first_chunk = nb.chunks[0]
        self.assertEqual(first_chunk.start_line, 1)
        self.assertEqual(first_chunk.end_line, 20)
        self.assertIn("spec_v2.md", first_chunk.to_citation().format_citation())
        self.assertEqual(first_chunk.to_citation().start_line, 1)
        self.assertEqual(first_chunk.to_citation().end_line, 20)

    def test_grounded_query_scoring_and_citations(self):
        nb = GroundedNotebook("nb-query-test", "Query Test")
        source1 = """# Section 4: Adapters Protocol
All L2 execution must route through L0 Adapters.
Circuit breaker rule: 5 consecutive failures triggers an open breaker for 60 seconds.
Every adapter must support real dry_run mode without state mutation.
"""
        source2 = """# Section 15: Security & Fencing
Tokens must be validated cryptographically.
Fencing tokens prevent split-brain execution across multiple workers.
All kill-switch triggers must fail-closed immediately.
"""
        nb.ingest_text(source1, source_name="section4_adapters.md")
        nb.ingest_text(source2, source_name="section15_security.md")

        # Query about circuit breaker
        res = nb.query("circuit breaker consecutive failures open breaker", top_k=2)
        self.assertIsInstance(res, GroundedQueryResult)
        self.assertGreater(res.total_chunks_matched, 0)
        self.assertIn("section4_adapters.md", res.citations[0]["citation"])
        self.assertIn("60 seconds", res.synthesized_context)

        # Query about fencing
        res2 = nb.query("fencing tokens split-brain execution", top_k=2)
        self.assertGreater(res2.total_chunks_matched, 0)
        self.assertIn("section15_security.md", res2.citations[0]["citation"])

    def test_multi_source_synthesis(self):
        nb = GroundedNotebook("nb-synth-test", "Synthesis Test")
        nb.ingest_text("Marzneshin enforces fail-closed kill-switch mechanisms.", "kill_switch.md")
        nb.ingest_text("Fail-closed mechanisms ensure safety during cluster partitions.", "network_spec.md")

        synth = nb.synthesize("fail-closed mechanisms", top_k=3)
        self.assertIsInstance(synth, SourceSynthesis)
        self.assertIn("kill_switch.md", synth.sources_consulted)
        self.assertIn("network_spec.md", synth.sources_consulted)
        self.assertIn("Grounded Insights", synth.summary)

    def test_grounding_verification_supported_vs_unsupported(self):
        nb = GroundedNotebook("nb-verify-test", "Verification Test")
        spec_text = """
The L0 adapter requires 9 contract checks: C1 through C9.
Check C5 tests idempotency per declared class.
Check C6 validates that dry_run performs zero state mutations.
"""
        nb.ingest_text(spec_text, "adapter_contract.md")

        # Statement fully supported by source
        verif_supported = nb.verify_grounding("Check C6 validates dry_run performs zero state mutations.")
        self.assertIsInstance(verif_supported, GroundingVerification)
        self.assertTrue(verif_supported.supported)
        self.assertGreater(verif_supported.confidence, 0.4)
        self.assertGreater(len(verif_supported.supporting_citations), 0)

        # Statement completely ungrounded / hallucinated
        verif_hallucinated = nb.verify_grounding("The system uses quantum teleportation and blockchain voting.")
        self.assertFalse(verif_hallucinated.supported)
        self.assertLess(verif_hallucinated.confidence, 0.2)
        self.assertGreater(len(verif_hallucinated.unsupported_aspects), 0)

    def test_store_persistence_lifecycle(self):
        nb = GroundedNotebook("nb-persist-01", "Persist Test", "Persistence test description")
        nb.ingest_text("Durable knowledge fact.", "fact.txt")
        saved_path = self.store.save(nb)
        self.assertTrue(saved_path.is_file())

        loaded = self.store.load("nb-persist-01")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.title, "Persist Test")
        self.assertEqual(len(loaded.sources), 1)
        self.assertEqual(len(loaded.chunks), 1)

        listed = self.store.list_all()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["notebook_id"], "nb-persist-01")

        deleted = self.store.delete("nb-persist-01")
        self.assertTrue(deleted)
        self.assertIsNone(self.store.load("nb-persist-01"))


if __name__ == "__main__":
    unittest.main()
