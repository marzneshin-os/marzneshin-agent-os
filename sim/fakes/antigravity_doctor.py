"""Fake Adapter for Antigravity Doctor & Health Recovery Engine.

Must pass the exact same contract test (adapters.contract.run_contract) as the real adapter.
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
from scripts.lib import clock


class AntigravityDoctorFake(Adapter):
    """Simulation Fake for AntigravityDoctorAdapter."""

    name = "antigravity_doctor"

    def __init__(
        self,
        world_state=None,
        *,
        seed: int = 0,
        world: World = "sim",
    ) -> None:
        self.world = world
        self._w = world_state
        self._seed = seed
        self._circuit = CircuitBreaker(threshold=5, reset_after_s=60.0)
        self._idem = IdempotencyStore()

        # Fault injection
        self.fail_healthz = False
        self.fail_next_execute = False
        self.fail_as_refused = False

    def healthz(self) -> Health:
        if self.fail_healthz:
            return Health(ok=False, detail="Injected Antigravity Doctor failure", latency_ms=1.5)
        return Health(ok=True, detail="Antigravity Doctor (simulated ok)", latency_ms=10.0)

    def capabilities(self) -> list[str]:
        return [
            "diagnose_account",
            "clean_credentials",
            "repair_environment",
            "check_eligibility",
            "get_auth_status",
        ]

    def execute(
        self,
        op: str,
        args: dict[str, Any],
        *,
        idem_key: str,
        idem_class: IdemClass = "none",
        dry_run: bool = False,
        deadline: datetime,
        provenance: list[dict[str, Any]],
    ) -> Result:
        self._circuit.before_call()

        if op not in self.capabilities():
            raise AdapterRefused(f"unknown op {op!r} on fake {self.name!r}")

        cached = self._idem.lookup(idem_key)
        if cached is not None:
            return cached

        rem = deadline_remaining_s(deadline)
        if rem <= 0:
            raise AdapterRefused(f"deadline expired ({rem:.2f}s remaining)")

        if self.fail_as_refused:
            raise AdapterRefused("Injected refusal from simulation")

        if self.fail_next_execute:
            self.fail_next_execute = False
            self._circuit.on_failure()
            raise RuntimeError("Injected execute crash from simulation")

        if op == "diagnose_account":
            data = {
                "status": "HEALTHY",
                "platform": "sim",
                "active_email": "developer@gmail.com",
                "is_workspace_account": False,
                "issues": [],
                "next_actions": [],
            }
        elif op == "clean_credentials":
            data = {
                "ok": True,
                "removed_credentials": ["sim:gemini:antigravity"],
                "cleared_caches": ["sim:~/.gemini/antigravity.lock"],
                "terminated_processes": [],
                "errors": [],
            }
        elif op == "repair_environment":
            data = {
                "ok": True,
                "clean_result": {"ok": True},
                "reauth_guidance": {"step1": "Complete age verification"},
                "issues_resolved": ["credentials_cleared"],
            }
        elif op == "check_eligibility":
            email = args.get("email", "dev@gmail.com")
            is_ws = not email.endswith("@gmail.com")
            data = {
                "email": email,
                "is_workspace": is_ws,
                "eligible": not is_ws,
            }
        elif op == "get_auth_status":
            data = {
                "status": "HEALTHY",
                "active_email": "developer@gmail.com",
                "is_workspace": False,
                "issues_count": 0,
            }
        else:
            raise AdapterRefused(f"unhandled op: {op}")

        result = Result(
            ok=True,
            op=op,
            data=data,
            dry_run=dry_run,
            attempts=1,
        )
        self._circuit.on_success()
        if idem_class != "none":
            self._idem.save(idem_key, result, klass=idem_class)
        return result

    def rollback(self, receipt_ref: str) -> Result:
        return Result(ok=True, op="rollback", data={"ref": receipt_ref, "status": "rolled_back"})
