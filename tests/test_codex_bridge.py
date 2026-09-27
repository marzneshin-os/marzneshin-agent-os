#!/usr/bin/env python3
"""Unit tests for codex_bridge.py."""

import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys
import tempfile
import json

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import codex_bridge


class TestCodexBridge(unittest.TestCase):
    def test_generate_receipt_structure(self):
        receipt = codex_bridge.generate_receipt(
            task_id="T-TEST-01",
            author="codex-author",
            reviewer="adversarial-reviewer",
            changes=["scripts/dev.py"],
            evidence="unit tests passed",
            verdict="APPROVED",
        )
        self.assertEqual(receipt["version"], "v2.0")
        self.assertEqual(receipt["task_id"], "T-TEST-01")
        self.assertEqual(receipt["author"]["id"], "codex-author")
        self.assertEqual(receipt["reviewer"]["id"], "adversarial-reviewer")
        self.assertEqual(receipt["verdict"], "APPROVED")
        self.assertIn("receipt_hash", receipt)
        self.assertIn("evidence_digest", receipt)
        self.assertEqual(len(receipt["receipt_hash"]), 64)

    def test_save_receipt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(codex_bridge, "REPO_ROOT", Path(tmpdir)):
                receipt = codex_bridge.generate_receipt(
                    task_id="T-SAVE-01",
                    author="a1",
                    reviewer="r1",
                    changes=["file.py"],
                    evidence="ok",
                )
                target = codex_bridge.save_receipt(receipt)
                self.assertTrue(target.exists())
                data = json.loads(target.read_text(encoding="utf-8"))
                self.assertEqual(data["task_id"], "T-SAVE-01")

    @patch("codex_bridge.run_verify_gate")
    def test_cmd_verify_pass(self, mock_gate):
        mock_gate.return_value = (True, "All passed")
        args = MagicMock()
        ret = codex_bridge.cmd_verify(args)
        self.assertEqual(ret, 0)

    @patch("codex_bridge.run_verify_gate")
    def test_cmd_verify_fail(self, mock_gate):
        mock_gate.return_value = (False, "Invariant broken")
        args = MagicMock()
        ret = codex_bridge.cmd_verify(args)
        self.assertEqual(ret, 1)


if __name__ == "__main__":
    unittest.main()
