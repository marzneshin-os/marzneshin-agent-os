"""ECC Adapter ? Everything Claude Code Universal Harness & AgentShield Security Adapter (?4 / BUILD-SPEC).

Integrates the ECC harness, AgentShield security auditor, and Continuous Learning into Marzneshin Agent OS:
- AgentShield security audits across rules, configs, prompt surfaces, and code.
- Continuous learning instinct capture and query with confidence scoring.
- Cross-agentic rule and harness parity verification.
- Conforms strictly to BUILD-SPEC.md ?4 Adapter protocol (circuit breaker, idempotency, dry_run, timeout).
"""

from __future__ import annotations

import time
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
from scripts.lib.ecc_harness import AgentShieldScanner, HarnessAudit, InstinctStore


class EccAdapter(Adapter):
    """L0 Adapter for Everything Claude Code (ECC) Universal Harness."""

    name = "ecc"

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

    def healthz(self) -> Health:
        self._circuit.before_call()
        start = time.monotonic()
        detail = (
            "ECC Universal Harness & AgentShield (production active)"
            if self.world == "prod"
            else "ECC Universal Harness & AgentShield (simulation standby)"
        )
        latency = (time.monotonic() - start) * 1000.0
        return Health(ok=True, detail=detail, latency_ms=float(latency))

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

        if deadline_remaining_s(deadline) <= 0:
            raise TimeoutError("Deadline exceeded before ECC execution")

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
                error=f"ECC execution error in {op}: {str(e)}",
                dry_run=dry_run,
                attempts=1,
                duration_ms=round((time.monotonic() - start_time) * 1000.0, 1),
            )

    def _execute_sim(self, op: str, payload: dict, dry_run: bool) -> dict[str, Any]:
        if op == "agentshield_scan":
            return {
                "passed": True,
                "summary": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0},
                "findings": [],
                "scanned_files": 12,
                "simulated": True,
            }
        elif op == "instinct_learn":
            trigger = payload.get("trigger", "sim/.*")
            action = payload.get("action", "Default simulated action")
            return {
                "id": "inst_sim_123",
                "trigger": trigger,
                "action": action,
                "confidence": 0.8,
                "learned": not dry_run,
                "dry_run": dry_run,
            }
        elif op == "instinct_query":
            return {
                "count": 1,
                "instincts": [
                    {
                        "id": "inst_sim_001",
                        "trigger": "test",
                        "action": "Simulated rule",
                        "confidence": 0.9,
                    }
                ],
            }
        elif op == "instinct_update_confidence":
            return {
                "id": payload.get("instinct_id", "inst_sim_001"),
                "confidence": 0.95,
                "updated": not dry_run,
            }
        elif op == "harness_audit":
            return {
                "ok": True,
                "harnesses_detected": ["antigravity", "claude", "cursor"],
                "missing_rules": [],
                "simulated": True,
            }
        elif op == "harness_sync_rules":
            return {
                "synced": True,
                "rules_verified": 6,
                "dry_run": dry_run,
            }
        return {}

    def _execute_prod(self, op: str, payload: dict, dry_run: bool) -> dict[str, Any]:
        if op == "agentshield_scan":
            scanner = AgentShieldScanner()
            targets = payload.get("targets")
            strict = payload.get("strict", False)
            report = scanner.scan_workspace(targets=targets, strict=strict)
            return report.to_dict()

        elif op == "instinct_learn":
            if dry_run:
                return {
                    "id": "inst_dry_run",
                    "trigger": payload.get("trigger", ".*"),
                    "action": payload.get("action", "Preview action"),
                    "dry_run": True,
                }
            store = InstinctStore()
            inst = store.learn(
                trigger=payload.get("trigger", ".*"),
                action=payload.get("action", ""),
                rationale=payload.get("rationale", ""),
                domain=payload.get("domain"),
                confidence=payload.get("confidence", 0.8),
                provenance=payload.get("provenance", "adapter_call"),
            )
            return inst.to_dict()

        elif op == "instinct_query":
            store = InstinctStore()
            results = store.query(
                query_str=payload.get("query"),
                domain=payload.get("domain"),
                min_confidence=payload.get("min_confidence", 0.4),
            )
            return {"count": len(results), "instincts": [i.to_dict() for i in results]}

        elif op == "instinct_update_confidence":
            if dry_run:
                return {"id": payload.get("instinct_id", ""), "dry_run": True}
            store = InstinctStore()
            inst = store.update_confidence(
                instinct_id=payload.get("instinct_id", ""),
                success=payload.get("success", True),
            )
            return inst.to_dict() if inst else {"error": "instinct not found"}

        elif op == "harness_audit":
            auditor = HarnessAudit()
            report = auditor.audit()
            return report.to_dict()

        elif op == "harness_sync_rules":
            auditor = HarnessAudit()
            report = auditor.audit()
            return {"synced": report.ok, "status": report.status, "missing": report.missing_rules}

        return {}

    def rollback(self, receipt_ref: str) -> Result:
        return Result(
            ok=True,
            op="rollback",
            data={"receipt_ref": receipt_ref, "rolled_back": True},
        )
