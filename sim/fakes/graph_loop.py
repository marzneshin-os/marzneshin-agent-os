"""sim/fakes/graph_loop.py — Fake GraphLoop adapter for simulation scenarios (§16)."""

from __future__ import annotations

import time
from datetime import datetime
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


class GraphLoopFake(Adapter):
    name = "graph_loop"

    def __init__(self, world_state=None, *, seed: int = 0, world: World = "sim"):
        self.world = world
        self._w = world_state
        self._seed = seed
        self._circuit = CircuitBreaker(threshold=5, reset_after_s=60.0)
        self._idem = IdempotencyStore()
        self.learned_constraints = [
            "Always enforce fail-closed safety controls (§4)",
            "Return the unit, not the batch on verification failure",
        ]

    def healthz(self) -> Health:
        self._circuit.before_call()
        return Health(ok=True, detail="GraphLoopFake (sim)", latency_ms=0.5)

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
            raise TimeoutError("Deadline exceeded before GraphLoopFake execution")

        if op not in self.capabilities():
            raise AdapterRefused(f"Unsupported op: {op}")

        hit = self._idem.lookup(idem_key)
        if hit is not None:
            return hit

        t0 = time.monotonic()
        data = self._execute_op(op, payload, dry_run=dry_run)
        res = Result(
            ok=True,
            op=op,
            data=data,
            dry_run=dry_run,
            attempts=1,
            duration_ms=round((time.monotonic() - t0) * 1000.0, 1),
        )
        self._circuit.on_success()

        if idem_class in ("forever", "scoped") and not dry_run:
            self._idem.save(idem_key, res, klass=idem_class)

        return res

    def _execute_op(self, op: str, payload: dict, dry_run: bool) -> Any:
        if op == "get_learned_constraints":
            return {"constraints": list(self.learned_constraints), "count": len(self.learned_constraints)}

        elif op == "execute_code_transform":
            operation = payload.get("operation", "deduplicate")
            p = payload.get("payload", {})
            if operation == "deduplicate":
                items = p.get("items", [])
                return {"task_result": {"status": "SUCCESS", "verdict": "GREEN", "summary": f"Deduped {len(items)} items"}}
            return {"task_result": {"status": "SUCCESS", "verdict": "GREEN", "summary": "Code transform executed"}}

        elif op == "evaluate_gate":
            res = payload.get("task_result", {})
            br = res.get("blast_radius", "contained")
            if br == "irreversible" and not payload.get("allow_irreversible", False):
                return {"verdict": "BLOCKED", "blast_radius": br, "reason": "Irreversible action requires authorization"}
            return {"verdict": "GREEN", "blast_radius": br, "reason": "Gate checks passed"}

        elif op == "run_pipeline":
            return {
                "thread_id": "sim-thread-123",
                "objective": payload.get("objective", "Sim objective"),
                "final_report": "Simulated multi-agent cycle completed.",
                "total_completed": 2,
                "gate_verdicts": [{"verdict": "GREEN"}],
                "learned_constraints_count": len(self.learned_constraints)
            }

        raise AdapterRefused(f"Unsupported op: {op}")

    def rollback(self, receipt_ref: str) -> Result:
        return Result(
            ok=True,
            op="rollback",
            data={"receipt_ref": receipt_ref, "status": "rolled_back"},
            dry_run=False,
            attempts=1,
            duration_ms=1.0,
        )
