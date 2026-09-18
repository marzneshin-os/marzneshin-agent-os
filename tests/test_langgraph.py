import unittest
import os
import uuid

try:
    from langchain_core.messages import HumanMessage
    _LANGCHAIN_AVAILABLE = True
except ImportError:
    _LANGCHAIN_AVAILABLE = False

@unittest.skipUnless(_LANGCHAIN_AVAILABLE, "langchain_core not installed (optional dependency)")

class TestLangGraphMCP(unittest.TestCase):
    def setUp(self):
        # We ensure sqlite doesn't block by creating a unique test db path
        self.test_db_path = "state/langgraph_checkpoints_test.sqlite"
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
    
    def test_workflow_initialization(self):
        # We verify that the workflow imports and compiles without syntax errors
        try:
            from agents.langgraph_workflow import app
            self.assertIsNotNone(app)
            self.assertEqual(app.name, "LangGraph")
        except Exception as e:
            self.fail(f"Graph compilation failed: {e}")

    def test_nodes_exist(self):
        # Verify all nodes are wired up correctly
        from agents.langgraph_workflow import workflow
        nodes = workflow.nodes
        self.assertIn("Supervisor", nodes)
        self.assertIn("Coder", nodes)
        self.assertIn("Reviewer", nodes)
        self.assertIn("Memory", nodes)

    def test_mcp_server_tools_list(self):
        # Verify MCP server instance and its tool definitions
        try:
            import asyncio
            from scripts.langgraph_mcp import handle_list_tools
            tools = asyncio.run(handle_list_tools())
            tool_names = [t.name for t in tools]
            self.assertIn("start_multiagent_task", tool_names)
            self.assertIn("check_task_status", tool_names)
            self.assertIn("provide_feedback", tool_names)
        except Exception as e:
            self.fail(f"MCP server tools failed: {e}")

if __name__ == "__main__":
    unittest.main()
