"""Simulation fake for AWSBedrockAdapter (BUILD-SPEC §4 / ADR-029).

Enforces identical contract behavior with zero network calls and deterministic clock.
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


class AWSBedrockFake(Adapter):
    """Deterministic simulation fake for AWS Bedrock credit pool adapter."""

    name = "aws_bedrock"

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
        self._credits_remaining = 100.0
        self._spent = 0.0

    def healthz(self) -> Health:
        self._circuit.before_call()
        return Health(ok=True, detail="AWS Bedrock Fake (simulation)", latency_ms=0.5)

    def capabilities(self) -> list[str]:
        return [
            "bedrock_invoke_model",
            "bedrock_converse",
            "bedrock_check_credits",
            "bedrock_rotate_account",
            "bedrock_onboarding_checklist",
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
            raise TimeoutError("Deadline exceeded")

        if op not in self.capabilities():
            raise AdapterRefused(f"Unknown operation: {op}")

        hit = self._idem.lookup(idem_key)
        if hit is not None:
            return hit

        start = clock.now()
        data: dict[str, Any] = {}

        if op == "bedrock_invoke_model":
            model = payload.get("model", "anthropic.claude-3-5-sonnet-20241022-v2:0")
            prompt = payload.get("prompt", "")
            cost = 0.0001
            if not dry_run:
                self._spent += cost
                self._credits_remaining -= cost
            data = {
                "simulated": True,
                "model": model,
                "output_text": f"Fake response for: {prompt[:20]}",
                "cost_usd": cost,
                "remaining_usd": round(self._credits_remaining, 4),
            }

        elif op == "bedrock_converse":
            data = {
                "simulated": True,
                "response_message": {"role": "assistant", "content": "Fake converse response"},
            }

        elif op == "bedrock_check_credits":
            data = {
                "total_remaining_usd": round(self._credits_remaining, 2),
                "total_spent_usd": round(self._spent, 2),
                "active_account_id": "fake_builder_id",
            }

        elif op == "bedrock_rotate_account":
            data = {"rotated": True, "active_account_id": "fake_builder_id_rotated"}

        elif op == "bedrock_onboarding_checklist":
            data = {"account_id": "fake_builder_id", "tasks_completed": 5}

        duration = round((clock.now() - start).total_seconds() * 1000.0, 1)
        res = Result(
            ok=True,
            op=op,
            data=data,
            dry_run=dry_run,
            attempts=1,
            duration_ms=duration,
        )
        self._circuit.on_success()

        if idem_class != "none" and not dry_run:
            self._idem.save(idem_key, res, klass=idem_class)

        return res

    def rollback(self, receipt_path: str) -> Result:
        return Result(ok=True, op="rollback", data={"receipt": receipt_path, "status": "NOOP"}, attempts=1, duration_ms=0.1)
