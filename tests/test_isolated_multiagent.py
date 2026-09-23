import unittest
import os
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.graph_state import AgentState, TaskSpec, TaskResult
from agents.graph_nodes import (
    read_workspace_file,
    write_workspace_file,
    run_terminal_command,
    list_workspace_dir,
    coder_node,
    reviewer_node,
    supervisor_node,
    aggregator_node,
)
from agents.langgraph_workflow import workflow, app as graph_app


class TestIsolatedMultiAgent(unittest.TestCase):

    def test_state_isolation_contracts(self):
        """Verify TaskSpec and TaskResult isolate context without message bleeding."""
        task: TaskSpec = {
            "task_id": "T-TEST",
            "assigned_to": "Coder",
            "title": "Unit Test Task",
            "description": "Perform isolated operation",
            "target_files": ["state/test_file.txt"],
            "memory_context": "Sample architecture context",
            "iteration": 1
        }
        self.assertEqual(task["task_id"], "T-TEST")

        result: TaskResult = {
            "task_id": "T-TEST",
            "worker": "coder",
            "status": "SUCCESS",
            "summary": "Completed without context bleed",
            "artifacts_created": ["state/test_file.txt"],
            "test_output": "All checks green",
            "tests_passed": True,
            "error": None
        }
        self.assertEqual(result["status"], "SUCCESS")
        self.assertNotIn("messages", result, "TaskResult must not contain bloated messages")

    def test_operational_workspace_tools(self):
        """Verify worker operational tools execute safely against workspace."""
        # 1. read_workspace_file
        readme_content = read_workspace_file.invoke("README.md")
        self.assertIn("Marzneshin", readme_content)

        # 2. write_workspace_file
        test_file = "state/scratch_tool_test.txt"
        write_res = write_workspace_file.invoke({"relative_path": test_file, "content": "Tool test content"})
        self.assertIn("Successfully wrote", write_res)
        self.assertTrue((REPO_ROOT / test_file).exists())
        (REPO_ROOT / test_file).unlink(missing_ok=True)

        # 3. run_terminal_command
        cmd_res = run_terminal_command.invoke("echo 'MARZNESHIN_TOOL_OK'")
        self.assertIn("Exit Code: 0", cmd_res)
        self.assertIn("MARZNESHIN_TOOL_OK", cmd_res)

        # 4. list_workspace_dir
        dir_res = list_workspace_dir.invoke("agents")
        self.assertIn("graph_nodes.py", dir_res)
        self.assertIn("graph_state.py", dir_res)

    def test_coder_node_isolated_execution(self):
        """Verify coder_node receives a TaskSpec and returns a concise TaskResult."""
        task: TaskSpec = {
            "task_id": "T-CODER-1",
            "assigned_to": "Coder",
            "title": "Mock Task",
            "description": "Verify isolated coder execution",
            "target_files": [],
            "memory_context": ""
        }
        out = coder_node(task)
        self.assertIn("completed_results", out)
        self.assertEqual(len(out["completed_results"]), 1)
        res = out["completed_results"][0]
        self.assertEqual(res["task_id"], "T-CODER-1")
        self.assertEqual(res["worker"], "coder")
        self.assertTrue(len(res["summary"]) > 0)
        self.assertNotIn("messages", out, "Worker must not leak raw message objects to global state")

    def test_reviewer_node_isolated_execution(self):
        """Verify reviewer_node executes quality checks and returns a TaskResult."""
        task: TaskSpec = {
            "task_id": "T-REV-1",
            "title": "Review Quality Gate"
        }
        out = reviewer_node(task)
        self.assertIn("completed_results", out)
        res = out["completed_results"][0]
        self.assertEqual(res["worker"], "reviewer")
        self.assertIn("Reviewer verification gate", res["summary"])

    def test_workflow_topology_nodes(self):
        """Verify all parallel and aggregator nodes exist in the graph."""
        nodes = workflow.nodes
        self.assertIn("Supervisor", nodes)
        self.assertIn("Coder", nodes)
        self.assertIn("Reviewer", nodes)
        self.assertIn("Aggregator", nodes)
        self.assertIn("Memory", nodes)

    def test_end_to_end_graph_execution(self):
        """Verify full graph execution with parallel dispatch and aggregation."""
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        initial_state: AgentState = {
            "objective": "Verify isolated multiagent engine",
            "current_task": "Verify isolated multiagent engine",
            "pending_tasks": [],
            "completed_results": [],
            "iteration": 0,
            "max_iterations": 2,
            "active_workers": ["Supervisor", "Coder", "Reviewer"]
        }

        # Run stream
        executed_nodes = []
        for update in graph_app.stream(initial_state, config):
            executed_nodes.append(list(update.keys())[0])

        self.assertIn("Supervisor", executed_nodes)
        self.assertTrue(len(executed_nodes) >= 2)

        # Retrieve final state
        state = graph_app.get_state(config)
        self.assertIsNotNone(state)
        results = state.values.get("completed_results", [])
        self.assertTrue(len(results) >= 1)


if __name__ == "__main__":
    unittest.main()
