"""Unit tests for agent_activity_monitor.py (scripts/agent_activity_monitor.py)."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(1, str(REPO / "scripts"))

from scripts.agent_activity_monitor import (
    Colors,
    find_latest_conversation,
    format_tool_call,
    get_brain_dir,
)


import re

def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TestFormatToolCall(unittest.TestCase):
    def test_empty_and_invalid_tool_call(self):
        # Non-dict inputs
        self.assertIn("[Tool] unknown", strip_ansi(format_tool_call(None)))  # type: ignore[arg-type]
        self.assertIn("[Tool] unknown", strip_ansi(format_tool_call("not a dict")))  # type: ignore[arg-type]
        # Empty dict
        self.assertIn("[Tool] unknown", strip_ansi(format_tool_call({})))
        # Dict with None or empty name
        self.assertIn("[Tool] unknown", strip_ansi(format_tool_call({"name": None})))
        self.assertIn("[Tool] unknown", strip_ansi(format_tool_call({"name": ""})))

    def test_null_values_pyrefly_repro(self):
        """Reproduce Pyrefly issue where CommandLine, TargetFile, or Path are explicitly None."""
        # 1. CommandLine is None
        res_cmd = format_tool_call({"name": "run_command", "args": {"CommandLine": None}})
        self.assertIn("run_command", res_cmd)
        self.assertNotIn("None", res_cmd)

        # 2. TargetFile is None
        res_tf = format_tool_call({"name": "write_to_file", "args": {"TargetFile": None}})
        self.assertIn("write_to_file", res_tf)
        self.assertNotIn("None", res_tf)

        # 3. Path is None
        res_p = format_tool_call({"name": "read_file", "args": {"Path": None}})
        self.assertIn("read_file", res_p)
        self.assertNotIn("None", res_p)

        # 4. AbsolutePath is None
        res_ap = format_tool_call({"name": "view_file", "args": {"AbsolutePath": None}})
        self.assertIn("view_file", res_ap)
        self.assertNotIn("None", res_ap)

        # 5. Combined None fields
        res_all_none = format_tool_call({
            "name": "multi_tool",
            "args": {
                "CommandLine": None,
                "TargetFile": None,
                "Path": None,
                "AbsolutePath": None,
                "file_path": None,
                "path": None,
            },
        })
        self.assertIn("multi_tool", res_all_none)
        self.assertNotIn("None", res_all_none)

        # 6. CommandLine is None, but valid TargetFile is provided
        res_fallback = format_tool_call({
            "name": "edit_tool",
            "args": {"CommandLine": None, "TargetFile": "/var/log/app.py"},
        })
        self.assertIn("edit_tool", res_fallback)
        self.assertIn("app.py", res_fallback)

    def test_tool_summary_extraction(self):
        res1 = format_tool_call({"name": "custom_tool", "args": {"toolSummary": "Analyzing codebase"}})
        self.assertIn("Analyzing codebase", res1)

        res2 = format_tool_call({"name": "custom_tool", "args": {"toolAction": "Deploying worker"}})
        self.assertIn("Deploying worker", res2)

    def test_command_line_formatting(self):
        # Short command
        res_short = format_tool_call({"name": "run_command", "args": {"CommandLine": "git status"}})
        self.assertIn("`git status`", res_short)

        # Long command (> 60 chars)
        long_cmd = "python3 -m pytest tests/test_deep_architecture_pipeline_verification.py --verbose --color=yes"
        res_long = format_tool_call({"name": "run_command", "args": {"CommandLine": long_cmd}})
        self.assertIn("...", res_long)
        self.assertIn(f"`{long_cmd[:60]}...`", res_long)

        # Empty string command
        res_empty = format_tool_call({"name": "run_command", "args": {"CommandLine": ""}})
        self.assertIn("run_command", res_empty)

    def test_file_paths(self):
        test_cases = [
            ("TargetFile", "src/core/router.py", "router.py"),
            ("AbsolutePath", "/etc/hosts", "hosts"),
            ("Path", "docs/README.md", "README.md"),
            ("file_path", "tests/unit/test_foo.py", "test_foo.py"),
            ("path", "scripts/deploy.sh", "deploy.sh"),
            ("TargetFile", r"C:\Windows\System32\cmd.exe", "cmd.exe"),
        ]
        for key, raw_path, expected_name in test_cases:
            with self.subTest(key=key, path=raw_path):
                res = format_tool_call({"name": "file_op", "args": {key: raw_path}})
                self.assertIn(f"-> {expected_name}", res)

    def test_query_and_queries(self):
        # query
        res_q = format_tool_call({"name": "grep_search", "args": {"query": "def get_brain_dir"}})
        self.assertIn("query: `def get_brain_dir`", res_q)

        # long query (> 60 chars)
        long_q = "SELECT * FROM users WHERE status = 'active' AND last_login > '2026-01-01' ORDER BY id DESC"
        res_long_q = format_tool_call({"name": "db_search", "args": {"query": long_q}})
        self.assertIn("query: `" + long_q[:60] + "...`", res_long_q)

        # queries list
        res_qs = format_tool_call({"name": "batch_search", "args": {"queries": ["alpha", "beta", "gamma"]}})
        self.assertIn("queries: `[alpha, beta, gamma]`", res_qs)

    def test_prompt(self):
        res_p = format_tool_call({"name": "chat", "args": {"prompt": "Write a unit test for this service."}})
        self.assertIn("prompt: Write a unit test", res_p)

        # Multi-line prompt
        multiline_prompt = "First line of instruction\nSecond line of instruction\nThird line"
        res_multi = format_tool_call({"name": "chat", "args": {"prompt": multiline_prompt}})
        self.assertNotIn("\n", res_multi.split("-> prompt: ")[1])

    def test_task_and_conversation_id(self):
        res_task = format_tool_call({"name": "task_mgr", "args": {"TaskId": "task-42-boost"}})
        self.assertIn("id: task-42-boost", res_task)

        res_conv = format_tool_call({"name": "subagent", "args": {"conversationId": "cid-abc-123"}})
        self.assertIn("id: cid-abc-123", res_conv)

    def test_raw_string_args(self):
        # Valid JSON encoded string
        json_args = json.dumps({"CommandLine": "echo 'hello world'"})
        res_json = format_tool_call({"name": "run_command", "args": json_args})
        self.assertIn("`echo 'hello world'`", res_json)

        # Invalid JSON string should not crash
        res_invalid = format_tool_call({"name": "raw_tool", "args": "{not_valid_json:"})
        self.assertIn("[Tool]", res_invalid)
        self.assertIn("raw_tool", res_invalid)

        # Non-dict JSON string (e.g. list or int)
        res_list = format_tool_call({"name": "raw_tool", "args": "[1, 2, 3]"})
        self.assertIn("raw_tool", res_list)


class TestFindLatestConversation(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="test_conv_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_nonexistent_directory(self):
        nonexistent = self.test_dir / "does_not_exist"
        self.assertIsNone(find_latest_conversation(nonexistent))

    def test_empty_directory(self):
        self.assertIsNone(find_latest_conversation(self.test_dir))

    def test_directory_without_transcripts(self):
        (self.test_dir / "folder_a").mkdir()
        (self.test_dir / "folder_b").mkdir()
        (self.test_dir / "file.txt").write_text("hello", encoding="utf-8")
        self.assertIsNone(find_latest_conversation(self.test_dir))

    def test_mocked_conversations_picks_latest(self):
        conv1 = self.test_dir / "conv_older"
        conv2 = self.test_dir / "conv_newer"

        log1 = conv1 / ".system_generated" / "logs"
        log1.mkdir(parents=True)
        transcript1 = log1 / "transcript.jsonl"
        transcript1.write_text('{"step": 1}\n', encoding="utf-8")

        log2 = conv2 / ".system_generated" / "logs"
        log2.mkdir(parents=True)
        transcript2 = log2 / "transcript.jsonl"
        transcript2.write_text('{"step": 2}\n', encoding="utf-8")

        # Set older timestamp on transcript1 and newer timestamp on transcript2
        os.utime(transcript1, (1000000.0, 1000000.0))
        os.utime(transcript2, (2000000.0, 2000000.0))

        latest = find_latest_conversation(self.test_dir)
        self.assertIsNotNone(latest)
        self.assertEqual(latest, conv2)


class TestGetBrainDir(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="test_brain_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_antigravity_brain_dir_env_var(self):
        with patch.dict(os.environ, {"ANTIGRAVITY_BRAIN_DIR": str(self.test_dir)}):
            resolved = get_brain_dir()
            self.assertEqual(resolved, self.test_dir)

    def test_fallback_when_none_exist(self):
        # When none of the candidate directories exist
        with patch.dict(os.environ, {"ANTIGRAVITY_BRAIN_DIR": ""}):
            with patch.object(Path, "exists", return_value=False):
                res = get_brain_dir()
                self.assertIsInstance(res, Path)
                self.assertTrue(len(str(res)) > 0)


if __name__ == "__main__":
    unittest.main()
