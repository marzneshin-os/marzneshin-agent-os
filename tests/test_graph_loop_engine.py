import unittest
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.graph_state import AgentState, TaskSpec, TaskResult
from agents.code_nodes import (
    deduplicate_items,
    rank_items,
    verify_schema_compliance,
    check_diff_bounds,
    merge_task_results,
    code_node,
)
from agents.gate_nodes import evaluate_unit_gate, gate_node


class TestGraphLoopEngine(unittest.TestCase):

    def test_state_contracts_blast_radius_and_return_path(self):
        """Verify TaskSpec and TaskResult support blast radius and unit-level return contracts."""
        task: TaskSpec = {
            "task_id": "U-AUTH-1",
            "assigned_to": "Coder",
            "title": "Fix Auth Redirect",
            "description": "Fix redirect status code",
            "target_files": ["gateway/auth.py"],
            "scope_constraint": "gateway/auth.py",
            "blast_radius": "contained",
            "reversibility": "high",
            "attempts": 1,
            "max_attempts": 3,
            "verdict_evidence": "expected 302, got 200 at gateway/auth.py:88",
            "iteration": 1
        }
        self.assertEqual(task["blast_radius"], "contained")
        self.assertEqual(task["scope_constraint"], "gateway/auth.py")
        self.assertEqual(task["attempts"], 1)

        result: TaskResult = {
            "task_id": "U-AUTH-1",
            "worker": "coder",
            "status": "SUCCESS",
            "verdict": "GREEN",
            "blast_radius": "contained",
            "reversibility": "high",
            "summary": "Updated status code from 200 to 302",
            "artifacts_created": ["gateway/auth.py"],
            "test_output": "test_auth_redirect PASSED",
            "tests_passed": True,
            "scope_violations": [],
            "attempts_used": 1,
            "derived_constraint": "Auth redirects must issue HTTP 302 with Location header",
            "error": None
        }
        self.assertEqual(result["verdict"], "GREEN")
        self.assertEqual(result["derived_constraint"], "Auth redirects must issue HTTP 302 with Location header")
        self.assertEqual(len(result["scope_violations"]), 0)

    def test_code_node_deterministic_transformations(self):
        """Verify code nodes perform deterministic tasks with zero LLM variance."""
        # 1. Deduplication
        items = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}, {"id": 1, "name": "A_dup"}]
        deduped = deduplicate_items(items, key="id")
        self.assertEqual(len(deduped), 2)
        self.assertEqual(deduped[0]["name"], "A")
        self.assertEqual(deduped[1]["name"], "B")

        # 2. Ranking
        scored = [{"id": "x", "score": 10}, {"id": "y", "score": 90}, {"id": "z", "score": 50}]
        ranked = rank_items(scored, key="score", reverse=True)
        self.assertEqual(ranked[0]["id"], "y")
        self.assertEqual(ranked[1]["id"], "z")
        self.assertEqual(ranked[2]["id"], "x")

        # 3. Schema compliance
        data = {"task_id": "T1", "status": "SUCCESS"}
        ok, missing = verify_schema_compliance(data, ["task_id", "status", "summary"])
        self.assertFalse(ok)
        self.assertIn("summary", missing)

        ok2, missing2 = verify_schema_compliance(data, ["task_id", "status"])
        self.assertTrue(ok2)
        self.assertEqual(len(missing2), 0)

        # 4. Diff bounds & Scope checking
        targets = ["agents/graph_nodes.py"]
        modified_clean = ["agents/graph_nodes.py"]
        ok_diff, violations = check_diff_bounds(targets, modified_clean)
        self.assertTrue(ok_diff)

        modified_leak = ["agents/graph_nodes.py", "unauthorized/config.json"]
        ok_leak, violations_leak = check_diff_bounds(targets, modified_leak)
        self.assertFalse(ok_leak)
        self.assertTrue(any("unauthorized/config.json" in v for v in violations_leak))

        # 5. Direct LangGraph code_node execution
        task: TaskSpec = {
            "task_id": "CODE-DEDUP",
            "code_transform_op": "deduplicate",
            "code_transform_payload": {"items": items, "key": "id"}
        }
        res = code_node(task)
        self.assertIn("completed_results", res)
        c_res = res["completed_results"][0]
        self.assertEqual(c_res["worker"], "code_node")
        self.assertEqual(c_res["verdict"], "GREEN")
        self.assertEqual(c_res["status"], "SUCCESS")

    def test_gate_nodes_blast_radius_policy(self):
        """Verify blast-radius driven gate evaluation across Lane 1, 2, and 3."""
        # Lane 1: Contained - Passes on tests_passed
        res_contained: TaskResult = {
            "task_id": "U-1",
            "blast_radius": "contained",
            "reversibility": "high",
            "status": "SUCCESS",
            "tests_passed": True,
            "test_output": "All 5 unit tests passed",
            "scope_violations": [],
            "summary": "Isolated unit fix"
        }
        verdict_c = evaluate_unit_gate(res_contained)
        self.assertEqual(verdict_c["verdict"], "GREEN")

        # Lane 1: Contained - Fails on test failure
        res_contained_fail: TaskResult = {
            "task_id": "U-2",
            "blast_radius": "contained",
            "status": "FAILED",
            "tests_passed": False,
            "error": "AssertionError at test_auth.py:42",
            "scope_violations": []
        }
        verdict_cf = evaluate_unit_gate(res_contained_fail)
        self.assertEqual(verdict_cf["verdict"], "RED")
        self.assertIn("AssertionError", verdict_cf["evidence"])

        # Lane 1: Contained - Fails on scope creep
        res_contained_scope: TaskResult = {
            "task_id": "U-3",
            "blast_radius": "contained",
            "status": "SUCCESS",
            "tests_passed": True,
            "scope_violations": ["Scope violation: file 'configs/core.json' touched"],
        }
        verdict_cs = evaluate_unit_gate(res_contained_scope)
        self.assertEqual(verdict_cs["verdict"], "RED")
        self.assertIn("Scope violation", verdict_cs["reason"])

        # Lane 3: Irreversible - Fails closed by default
        res_irreversible: TaskResult = {
            "task_id": "U-MIGRATION",
            "blast_radius": "irreversible",
            "reversibility": "none",
            "status": "SUCCESS",
            "tests_passed": True,
            "summary": "Run production database migration"
        }
        verdict_ir = evaluate_unit_gate(res_irreversible, allow_irreversible=False)
        self.assertEqual(verdict_ir["verdict"], "BLOCKED")
        self.assertIn("Lane 3 Blast Radius", verdict_ir["reason"])

        # Lane 3: Irreversible - Opens only with explicit approval
        verdict_ir_approved = evaluate_unit_gate(res_irreversible, allow_irreversible=True)
        self.assertEqual(verdict_ir_approved["verdict"], "GREEN")

    def test_gate_node_unit_not_batch_return_path(self):
        """Verify that when 1 out of 4 tasks fails, ONLY the 1 failing unit is returned, preserving the 3 green ones."""
        results: list[TaskResult] = [
            {"task_id": "T1", "status": "SUCCESS", "tests_passed": True, "blast_radius": "contained", "artifacts_created": ["f1.py"], "summary": "Slice 1 ok"},
            {"task_id": "T2", "status": "SUCCESS", "tests_passed": True, "blast_radius": "contained", "artifacts_created": ["f2.py"], "summary": "Slice 2 ok"},
            {"task_id": "T3", "status": "FAILED", "tests_passed": False, "blast_radius": "contained", "artifacts_created": ["f3.py"], "error": "test_auth_redirect failed", "test_output": "expected 302 got 200 at auth.py:88"},
            {"task_id": "T4", "status": "SUCCESS", "tests_passed": True, "blast_radius": "contained", "artifacts_created": ["f4.py"], "summary": "Slice 4 ok"},
        ]

        state: AgentState = {
            "completed_results": results,
            "pending_tasks": [
                {"task_id": "T1", "scope_constraint": "f1.py", "target_files": ["f1.py"], "attempts": 1, "max_attempts": 3},
                {"task_id": "T2", "scope_constraint": "f2.py", "target_files": ["f2.py"], "attempts": 1, "max_attempts": 3},
                {"task_id": "T3", "scope_constraint": "f3.py", "target_files": ["f3.py"], "attempts": 1, "max_attempts": 3},
                {"task_id": "T4", "scope_constraint": "f4.py", "target_files": ["f4.py"], "attempts": 1, "max_attempts": 3},
            ],
            "iteration": 1,
            "max_iterations": 3,
            "learned_constraints": []
        }

        gate_out = gate_node(state)

        # 1. Exactly 1 unit returned (not the whole batch of 4!)
        rejected = gate_out["rejected_units"]
        self.assertEqual(len(rejected), 1, "Must return ONLY the failed unit, not the entire batch")
        self.assertEqual(rejected[0]["task_id"], "T3-fix")
        self.assertEqual(rejected[0]["attempts"], 2)
        self.assertEqual(rejected[0]["scope_constraint"], "f3.py")
        self.assertIn("expected 302 got 200", rejected[0]["verdict_evidence"])

        # 2. Learning edge accumulates constraints from the 3 green slices
        learned = gate_out["learned_constraints"]
        self.assertEqual(len(learned), 3)

        # 3. Router dispatches parallel fix for T3
        self.assertEqual(gate_out["next_agent"], "parallel_dispatch")


if __name__ == "__main__":
    unittest.main()
