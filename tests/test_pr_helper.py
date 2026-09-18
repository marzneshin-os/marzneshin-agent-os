#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

import pr

class TestPrHelper(unittest.TestCase):
    def test_format_title_with_task(self):
        title = pr.format_pr_title("Add GitHub CLI workflow", "T-GH-001")
        self.assertEqual(title, "[T-GH-001] Add GitHub CLI workflow")

    def test_format_title_without_task(self):
        title = pr.format_pr_title("Add GitHub CLI workflow", None)
        self.assertEqual(title, "Add GitHub CLI workflow")

    def test_format_title_already_prefixed(self):
        title = pr.format_pr_title("[T-GH-001] Add GitHub CLI workflow", "T-GH-001")
        self.assertEqual(title, "[T-GH-001] Add GitHub CLI workflow")

    def test_build_create_cmd(self):
        cmd = pr.build_gh_create_cmd(
            title="[T-1] Test PR",
            body="Description of change",
            draft=True,
            fill=False
        )
        self.assertIn("gh", cmd)
        self.assertIn("pr", cmd)
        self.assertIn("create", cmd)
        self.assertIn("--title", cmd)
        self.assertIn("[T-1] Test PR", cmd)
        self.assertIn("--body", cmd)
        self.assertIn("Description of change", cmd)
        self.assertIn("--draft", cmd)

    def test_build_create_cmd_with_fill(self):
        cmd = pr.build_gh_create_cmd(
            title=None,
            body=None,
            draft=False,
            fill=True
        )
        self.assertIn("gh", cmd)
        self.assertIn("pr", cmd)
        self.assertIn("create", cmd)
        self.assertIn("--fill", cmd)

if __name__ == "__main__":
    unittest.main()
