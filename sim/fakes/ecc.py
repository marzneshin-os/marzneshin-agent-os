"""Fake Adapter for Everything Claude Code (ECC) Universal Harness (?4 / BUILD-SPEC).

Passes the contract test suite (adapters/contract.py) for the simulation world.
"""

from __future__ import annotations

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


class EccFake(Adapter):
    name = "ecc"

    def __init__(self, world_state=None, *, seed: int = 0, world: World = "sim"):
        self.world = world
        self._w = world_state
        self._circuit = CircuitBreaker(threshold=5, reset_after_s=60.0)
        self._idem = IdempotencyStore()

        self.fail_healthz = False
        self.fail_next_execute = False
        self.fail_as_refused = False

        self._instincts: dict[str, dict[str, Any]] = {
            "inst_sim_001": {
                "id": "inst_sim_001",
                "trigger": "test",
                "action": "Simulated rule",
                "confidence": 0.9,
            }
        }

    def healthz(self) -> Health:
        if self.fail_healthz:
            return Health(ok=False, detail="Injected failure in ECC fake", latency_ms=1.0)
        return Health(ok=True, detail="ECC Universal Harness & AgentShield (simulation standby)", latency_ms=2.0)

    def capabilities(self) -> list[str]:
        return [
            "agentshield_scan",
            "instinct_learn",
            "instinct_query",
            "instinct_update_confidence",
            "harness_audit",
            "harness_sync_rules",
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

        if self.fail_next_execute:
            self.fail_next_execute = False
            self._circuit.on_failure()
            if self.fail_as_refused:
                raise AdapterRefused("Injected refusal in ECC fake")
            raise RuntimeError("Injected runtime failure in ECC fake")

        if deadline_remaining_s(deadline) <= 0:
            raise TimeoutError("Deadline exceeded before ECC execution")

        if op not in self.capabilities():
            raise AdapterRefused(f"Unknown operation: {op}")

        hit = self._idem.lookup(idem_key)
        if hit is not None:
            return hit

        data: dict[str, Any] = {}
        if op == "agentshield_scan":
            data = {
                "passed": True,
                "summary": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0},
                "findings": [],
                "scanned_files": 10,
                "simulated": True,
            }
        elif op == "instinct_learn":
            inst_id = payload.get("id", f"inst_sim_{len(self._instincts) + 1:03d}")
            if not dry_run:
                self._instincts[inst_id] = {
                    "id": inst_id,
                    "trigger": payload.get("trigger", "sim/.*"),
                    "action": payload.get("action", "Simulated action"),
                    "confidence": payload.get("confidence", 0.8),
                }
            data = {"id": inst_id, "learned": not dry_run, "dry_run": dry_run}
        elif op == "instinct_query":
            data = {"count": len(self._instincts), "instincts": list(self._instincts.values())}
        elif op == "instinct_update_confidence":
            inst_id = payload.get("instinct_id", "inst_sim_001")
            data = {"id": inst_id, "confidence": 0.95, "updated": not dry_run}
        elif op == "harness_audit":
            data = {
                "ok": True,
                "harnesses_detected": ["antigravity", "claude", "cursor"],
                "missing_rules": [],
                "simulated": True,
            }
        elif op == "harness_sync_rules":
            data = {"synced": True, "rules_verified": 6, "dry_run": dry_run}

        res = Result(
            ok=True,
            op=op,
            data=data,
            dry_run=dry_run,
            attempts=1,
            duration_ms=2.5,
        )

        self._circuit.on_success()
        if idem_class in ("forever", "scoped") and not dry_run:
            self._idem.save(idem_key, res, klass=idem_class)

        return res

    def rollback(self, receipt_ref: str) -> Result:
        return Result(ok=True, op="rollback", data={"receipt_ref": receipt_ref, "rolled_back": True})
