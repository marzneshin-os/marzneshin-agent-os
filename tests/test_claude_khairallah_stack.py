"""Test suite validating Claude Code 2026 Golden Stack configuration (ADR-032).

Verifies Tavily MCP, Task Master AI, Spec Kit, Superpowers commands, and official skills.
"""

import json
import re
import unittest
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

class TestClaudeKhairallahStack(unittest.TestCase):
    def test_settings_and_mcp_json_valid(self):
        settings_path = WORKSPACE_ROOT / ".claude" / "settings.json"
        self.assertTrue(settings_path.exists(), "settings.json must exist")
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
        
        allow_list = settings.get("permissions", {}).get("allow", [])
        self.assertIn("Bash(python3 scripts/taskmaster_cli.py *)", allow_list)
        self.assertIn("Bash(python3 scripts/mcp_tavily.py *)", allow_list)
        self.assertIn("mcp__tavily__*", allow_list)

        mcp_path = WORKSPACE_ROOT / ".mcp.json"
        self.assertTrue(mcp_path.exists(), ".mcp.json must exist")
        with open(mcp_path, "r", encoding="utf-8") as f:
            mcp_data = json.load(f)
        
        servers = mcp_data.get("mcpServers", {})
        self.assertIn("context7", servers)
        self.assertIn("tavily", servers)
        self.assertEqual(servers["tavily"]["command"], "python3")

    def test_commands_present_and_valid(self):
        commands_dir = WORKSPACE_ROOT / ".claude" / "commands"
        expected = [
            "brainstorm.md", "spec.md", "taskmaster.md", "tdd.md",
            "debug.md", "verify-completion.md", "deep-research.md", "new-skill.md"
        ]
        for cmd in expected:
            p = commands_dir / cmd
            self.assertTrue(p.exists(), f"Command {cmd} must exist")
            text = p.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---"), f"Command {cmd} must start with YAML frontmatter")
            self.assertIn("description:", text, f"Command {cmd} must contain description in frontmatter")

    def test_skills_present_and_valid(self):
        skills_dir = WORKSPACE_ROOT / ".claude" / "skills"
        expected = [
            "skill-creator", "frontend-design", "spec-kit",
            "context-engineering", "deep-research", "taskmaster"
        ]
        for sk in expected:
            p = skills_dir / sk / "SKILL.md"
            self.assertTrue(p.exists(), f"Skill {sk}/SKILL.md must exist")
            text = p.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---"), f"Skill {sk} must start with YAML frontmatter")
            self.assertIn("description:", text, f"Skill {sk} must contain description")

    def test_mcp_tavily_tools_and_execution(self):
        import scripts.mcp_tavily as mcp_tavily
        tool_names = [t["name"] for t in mcp_tavily.TOOLS_SPEC]
        self.assertIn("tavily_search", tool_names)
        self.assertIn("tavily_extract", tool_names)
        self.assertIn("tavily_crawl", tool_names)
        self.assertIn("tavily_map", tool_names)

        # Execute fallback search
        res = mcp_tavily.execute_tool("tavily_search", {"query": "Unit test query"})
        self.assertIn("Unit test query", res)

        # Execute crawl
        crawl_res = mcp_tavily.execute_tool("tavily_crawl", {"url": "https://example.com", "limit": 2})
        self.assertIn("https://example.com", crawl_res)

    def test_taskmaster_cli_parsing_and_dag(self):
        import scripts.taskmaster_cli as tm
        sample_spec = """# Test PRD
## Task 1: Initialize Database
- [ ] Create SQLite schema
- [ ] Run migration
## Task 2: Implement API Endpoints
- [ ] Add POST /login
- [ ] Add GET /profile
"""
        tasks = tm.parse_prd_into_tasks(sample_spec, "test_spec")
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0]["id"], "TASK-01")
        self.assertEqual(tasks[0]["depends_on"], [])
        self.assertEqual(tasks[1]["id"], "TASK-02")
        self.assertEqual(tasks[1]["depends_on"], ["TASK-01"])
        self.assertEqual(len(tasks[0]["acceptance_criteria"]), 2)

if __name__ == "__main__":
    unittest.main()