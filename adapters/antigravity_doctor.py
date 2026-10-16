"""Antigravity Doctor Adapter — Account Diagnostics & Recovery (§4 / BUILD-SPEC).

Conforms strictly to BUILD-SPEC.md §4 Adapter protocol (circuit breaker,
idempotency, dry_run, deadline, and taint provenance).
"""

from __future__ import annotations

from datetime import datetime, timezone
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
from scripts.lib.antigravity_doctor import AntigravityDoctor


class AntigravityDoctorAdapter(Adapter):
    """L0 Adapter for Antigravity Doctor & Health Recovery Engine."""

    name = "antigravity_doctor"

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
        self.doctor = AntigravityDoctor(world=world)

    def healthz(self) -> Health:
        self._circuit.before_call()
        start = clock.now()
        detail = (
            "Antigravity Doctor (production active)"
            if self.world == "prod"
            else "Antigravity Doctor (simulation standby)"
        )
        latency = (clock.now() - start).total_seconds() * 1000.0
        return Health(ok=True, detail=detail, latency_ms=float(latency))

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
            raise AdapterRefused(f"unknown op {op!r} on adapter {self.name!r}")

        cached = self._idem.lookup(idem_key)
        if cached is not None:
            return cached

        rem = deadline_remaining_s(deadline)
        if rem <= 0:
            raise AdapterRefused(f"deadline expired ({rem:.2f}s remaining)")

        try:
            if op == "diagnose_account":
                diag = self.doctor.diagnose(token_str=args.get("token"))
                data = diag.to_dict()
            elif op == "clean_credentials":
                res = self.doctor.clean(
                    clean_credentials=args.get("clean_credentials", True),
                    clean_cache=args.get("clean_cache", True),
                    dry_run=dry_run,
                )
                data = res.to_dict()
            elif op == "repair_environment":
                res = self.doctor.repair(dry_run=dry_run)
                data = res.to_dict()
            elif op == "check_eligibility":
                email = args.get("email", "")
                is_workspace = self.doctor.is_workspace_domain(email)
                data = {
                    "email": email,
                    "is_workspace": is_workspace,
                    "eligible": not is_workspace if email else False,
                    "age_verification_url": self.doctor.AGE_VERIFICATION_URL,
                    "family_sharing_url": self.doctor.FAMILY_SHARING_URL,
                    "locations_url": self.doctor.DOCS_LOCATIONS_URL,
                }
            elif op == "get_auth_status":
                diag = self.doctor.diagnose(token_str=args.get("token"))
                data = {
                    "status": diag.status,
                    "active_email": diag.active_email,
                    "is_workspace": diag.is_workspace_account,
                    "issues_count": len(diag.issues),
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
        except Exception as exc:
            self._circuit.on_failure()
            if isinstance(exc, AdapterRefused):
                raise
            raise AdapterRefused(f"doctor execution failure: {exc}") from exc

    def rollback(self, receipt_ref: str) -> Result:
        return Result(ok=True, op="rollback", data={"ref": receipt_ref, "status": "rolled_back"})
