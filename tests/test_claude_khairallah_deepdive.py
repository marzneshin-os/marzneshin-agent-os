"""Test suite validating Claude Code 2026 Deep-Dive extension (ADR-033).

Verifies Playwright MCP, FastMCP, Instructor Structured Outputs, Markdownify,
DB Inspector, MCPHub, Model Routing, and Codebase Memory integration.
"""

import json
import unittest
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

class TestClaudeKhairallahDeepDive(unittest.TestCase):
    def test_playwright_mcp_and_settings(self):
        mcp_path = WORKSPACE_ROOT / ".mcp.json"
        self.assertTrue(mcp_path.exists())
        with open(mcp_path, "r", encoding="utf-8") as f:
            mcp_data = json.load(f)
        self.assertIn("playwright", mcp_data["mcpServers"])
        self.assertEqual(mcp_data["mcpServers"]["playwright"]["args"], ["-y", "@playwright/mcp@latest"])

        settings_path = WORKSPACE_ROOT / ".claude" / "settings.json"
        self.assertTrue(settings_path.exists())
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
        allow = settings.get("permissions", {}).get("allow", [])
        self.assertIn("mcp__playwright__*", allow)
        self.assertIn("Bash(python3 scripts/mcphub_cli.py *)", allow)
        self.assertIn("Bash(python3 scripts/db_query_cli.py *)", allow)

    def test_deepdive_commands_exist_and_valid(self):
        commands_dir = WORKSPACE_ROOT / ".claude" / "commands"
        expected = [
            "playwright.md", "fastmcp.md", "structured.md", "pdf.md",
            "markdownify.md", "db-query.md", "mcphub.md", "router.md", "graphify.md"
        ]
        for cmd in expected:
            p = commands_dir / cmd
            self.assertTrue(p.exists(), f"Command {cmd} must exist")
            content = p.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("---"), f"Command {cmd} missing frontmatter")
            self.assertIn("description:", content)

    def test_deepdive_skills_exist_and_valid(self):
        skills_dir = WORKSPACE_ROOT / ".claude" / "skills"
        expected = [
            "playwright", "fastmcp", "structured-output",
            "pdf", "db-inspector", "model-routing"
        ]
        for sk in expected:
            p = skills_dir / sk / "SKILL.md"
            self.assertTrue(p.exists(), f"Skill {sk}/SKILL.md must exist")
            content = p.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("---"), f"Skill {sk} missing frontmatter")
            self.assertIn("description:", content)

    def test_structured_output_engine(self):
        import scripts.lib.structured_output as so
        schema = {
            "type": "object",
            "required": ["decision", "confidence"],
            "properties": {
                "decision": {"type": "string", "enum": ["APPROVE", "REJECT"]},
                "confidence": {"type": "number"}
            }
        }

        # Valid JSON code block
        resp = "Here is the response:\n```json\n{\"decision\": \"APPROVE\", \"confidence\": 0.95}\n```\nDone."
        res = so.enforce_structured_output(resp, schema)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.data["decision"], "APPROVE")
        self.assertEqual(res.data["confidence"], 0.95)

        # Invalid field value
        resp_invalid = "```json\n{\"decision\": \"MAYBE\", \"confidence\": 0.5}\n```"
        res_inv = so.enforce_structured_output(resp_invalid, schema)
        self.assertFalse(res_inv.is_valid)
        self.assertTrue(any("enum" in err for err in res_inv.errors))

    def test_fastmcp_harness(self):
        from scripts.lib.fastmcp_harness import FastMCP
        mcp = FastMCP("test-server")

        @mcp.tool(description="Add two numbers")
        def add(a: int, b: int) -> int:
            return a + b

        self.assertEqual(len(mcp.tools_spec), 1)
        spec = mcp.tools_spec[0]
        self.assertEqual(spec["name"], "add")
        self.assertIn("a", spec["inputSchema"]["properties"])
        self.assertEqual(spec["inputSchema"]["properties"]["a"]["type"], "integer")

        result = mcp.execute_tool("add", {"a": 3, "b": 4})
        self.assertEqual(result, "7")

    def test_mcphub_diagnostics(self):
        import scripts.mcphub_cli as mcphub
        servers = mcphub.load_mcp_servers()
        self.assertGreaterEqual(len(servers), 10)
        self.assertIn("playwright", servers)
        self.assertIn("context7", servers)

        res = mcphub.probe_server("tavily", servers["tavily"])
        self.assertIn("ONLINE", res["status"])

    def test_db_query_cli(self):
        import sqlite3
        import tempfile
        import scripts.db_query_cli as dbq
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
            db_path = Path(tf.name)
        try:
            init_conn = sqlite3.connect(db_path)
            init_conn.execute("CREATE TABLE checkpoints (thread_id TEXT, checkpoint_id TEXT)")
            init_conn.commit()
            init_conn.close()

            conn = dbq.get_connection(db_path)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [r["name"] for r in cur.fetchall()]
            self.assertIn("checkpoints", tables)
            conn.close()
        finally:
            db_path.unlink(missing_ok=True)

    def test_markdownify_cli(self):
        import scripts.markdownify_cli as mdf
        csv_sample = "name,role,status\nAlice,Architect,Active\nBob,Engineer,Active"
        md = mdf.convert_csv_to_markdown(csv_sample)
        self.assertIn("| Alice | Architect | Active |", md)
        self.assertIn("| --- | --- | --- |", md)

        html_sample = "<h1>Title</h1><p>Paragraph with <a href='https://example.com'>link</a></p>"
        html_md = mdf.convert_html_to_markdown(html_sample)
        self.assertIn("# Title", html_md)
        self.assertIn("[link](https://example.com)", html_md)

if __name__ == "__main__":
    unittest.main()