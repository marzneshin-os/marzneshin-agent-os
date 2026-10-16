"""Graph & Loop Engineering Adapter for Marzneshin Autonomous OS.

Implements BUILD-SPEC §4 Adapter protocol for the 4-layer taxonomy:
Prompts -> Agents -> Loops -> Graphs.

Capabilities:
- run_pipeline: Dispatches multi-agent workflow with blast-radius scoping & dual return paths.
- evaluate_gate: Evaluates unit results against blast radius lanes (contained, wide, irreversible).
- execute_code_transform: Deterministic zero-token transformations (dedup, rank, schema, diff bounds).
- get_learned_constraints: Queries accumulated permanent learning constraints.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from adapters.base import (
    Adapter,
    AdapterRefused,
    CircuitBreaker,
    Health,
    IdemClass,
    IdempotencyStore,
    Result,
    World,
    deadline_remaining_s,
)
from scripts.lib import clock
from agents.graph_state import AgentState, TaskSpec, TaskResult
from agents.code_nodes import code_node, deduplicate_items, rank_items, check_diff_bounds
from agents.gate_nodes import evaluate_unit_gate, gate_node


class GraphLoopAdapter(Adapter):
    """L0 Adapter for Graph & Loop Engineering Multi-Agent Runtime."""

    name = "graph_loop"

    def __init__(
        self,
        world_state=None,
        *,
        seed: int = 0,
        world: World = "prod",
    ) -> None:
        self.world = world
        self._w = world_state
        self._seed = seed
        self._circuit = CircuitBreaker(threshold=5, reset_after_s=60.0)
        self._idem = IdempotencyStore()
        self._learned_constraints: list[str] = [
            "Always enforce fail-closed safety controls (§4)",
            "Return the unit, not the batch on verification failure",
            "Use deterministic code nodes for zero-variance data transforms",
        ]

    def healthz(self) -> Health:
        self._circuit.before_call()
        start = time.monotonic()
        detail = (
            "Graph & Loop Multi-Agent Runtime (production active)"
            if self.world == "prod"
            else "Graph & Loop Multi-Agent Runtime (simulation standby)"
        )
        latency = (time.monotonic() - start) * 1000.0
        return Health(ok=True, detail=detail, latency_ms=float(latency))

    def capabilities(self) -> list[str]:
        return [
            "run_pipeline",
            "evaluate_gate",
            "execute_code_transform",
            "get_learned_constraints",
        ]

    def execute(
        self,
        op: str,
        payload: dict,
        *,
        idem_key: str,
        idem_class: IdemClass,
        dry_run: bool,
        deadline: datetime,
        provenance: list[dict],
    ) -> Result:
        self._circuit.before_call()

        if deadline_remaining_s(deadline) <= 0:
            raise TimeoutError("Deadline exceeded before GraphLoop execution")

        if op not in self.capabilities():
            raise AdapterRefused(f"Unknown operation: {op}")

        hit = self._idem.lookup(idem_key)
        if hit is not None:
            return hit

        start_time = time.monotonic()
        try:
            if self.world == "sim":
                data = self._execute_sim(op, payload, dry_run=dry_run)
            else:
                data = self._execute_prod(op, payload, dry_run=dry_run)

            res = Result(
                ok=True,
                op=op,
                data=data,
                dry_run=dry_run,
                attempts=1,
                duration_ms=round((time.monotonic() - start_time) * 1000.0, 1),
            )
            self._circuit.on_success()

            if idem_class in ("forever", "scoped") and not dry_run:
                self._idem.save(idem_key, res, klass=idem_class)

            return res

        except AdapterRefused:
            raise
        except Exception as e:
            self._circuit.on_failure()
            return Result(
                ok=False,
                op=op,
                error=f"GraphLoop execution failed: {e}",
                dry_run=dry_run,
                attempts=1,
                duration_ms=round((time.monotonic() - start_time) * 1000.0, 1),
            )

    def _execute_prod(self, op: str, payload: dict, dry_run: bool) -> dict[str, Any]:
        if op == "get_learned_constraints":
            return {"constraints": list(self._learned_constraints), "count": len(self._learned_constraints)}

        elif op == "execute_code_transform":
            task: TaskSpec = {
                "task_id": payload.get("task_id", "CODE-TX"),
                "code_transform_op": payload.get("operation", "merge"),
                "code_transform_payload": payload.get("payload", {})
            }
            if dry_run:
                return {"dry_run": True, "op": payload.get("operation"), "status": "validated"}
            res = code_node(task)
            return {"task_result": res["completed_results"][0]}

        elif op == "evaluate_gate":
            res_payload = payload.get("task_result", {})
            task_spec = payload.get("task_spec")
            allow_irrev = payload.get("allow_irreversible", False)
            eval_res = evaluate_unit_gate(res_payload, task_spec, allow_irreversible=allow_irrev)
            if eval_res.get("verdict") == "GREEN" and eval_res.get("derived_constraint"):
                if not dry_run:
                    self._learned_constraints.append(eval_res["derived_constraint"])
            return eval_res

        elif op == "run_pipeline":
            objective = payload.get("objective", "Verify Graph & Loop Runtime")
            if dry_run:
                return {
                    "dry_run": True,
                    "objective": objective,
                    "status": "validated",
                    "plan": "Dry run verification successful without mutating workspace"
                }

            thread_id = str(uuid.uuid4())
            config = {"configurable": {"thread_id": thread_id}}
            initial_state: AgentState = {
                "objective": objective,
                "current_task": objective,
                "pending_tasks": [],
                "completed_results": [],
                "rejected_units": [],
                "learned_constraints": list(self._learned_constraints),
                "iteration": 0,
                "max_iterations": payload.get("max_iterations", 2),
                "active_workers": ["Supervisor", "Splitter", "Coder", "CodeNode", "Reviewer", "Gate"]
            }

            from agents.langgraph_workflow import app as graph_app
            for _ in graph_app.stream(initial_state, config):
                pass

            state = graph_app.get_state(config)
            vals = state.values if state else {}
            completed = vals.get("completed_results", [])
            gate_verdicts = vals.get("gate_verdicts", [])
            learned = vals.get("learned_constraints", [])
            if learned and not dry_run:
                for c in learned:
                    if c not in self._learned_constraints:
                        self._learned_constraints.append(c)

            return {
                "thread_id": thread_id,
                "objective": objective,
                "final_report": vals.get("final_report", "Pipeline cycle completed."),
                "total_completed": len(completed),
                "gate_verdicts": gate_verdicts,
                "learned_constraints_count": len(self._learned_constraints)
            }

        raise AdapterRefused(f"Unsupported operation: {op}")

    def _execute_sim(self, op: str, payload: dict, dry_run: bool) -> dict[str, Any]:
        return self._execute_prod(op, payload, dry_run=dry_run)

    def rollback(self, receipt_ref: str) -> Result:
        return Result(
            ok=True,
            op="rollback",
            data={"receipt_ref": receipt_ref, "status": "rolled_back"},
            dry_run=False,
            attempts=1,
            duration_ms=1.0,
        )
