"""Fake Adapter for FreeLLMAPI Universal Free-Tier Token Pool & Gateway.

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


class FreeLLMFake(Adapter):
    """Simulation Fake for FreeLLMAdapter."""

    name = "freellm"

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
            return Health(ok=False, detail="Injected FreeLLM failure", latency_ms=1.5)
        return Health(ok=True, detail="FreeLLM Universal Pool (simulated ok)", latency_ms=10.0)

    def capabilities(self) -> list[str]:
        return [
            "llm_chat",
            "llm_messages",
            "pool_status",
            "rotate_key",
            "test_provider",
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
        if op not in self.capabilities():
            return Result(ok=False, op=op, error=f"unknown op: {op}")

        stored = self._idem.lookup(idem_key)
        if stored:
            return stored

        if dry_run:
            res = Result(
                ok=True,
                op=op,
                dry_run=True,
                data={"simulated": True, "dry_run": True},
                attempts=1,
            )
            self._idem.save(idem_key, res, klass=idem_class)
            return res

        self._circuit.before_call()

        if deadline_remaining_s(deadline) <= 0:
            return Result(ok=False, op=op, error="deadline exceeded")

        if self.fail_next_execute:
            self.fail_next_execute = False
            if self.fail_as_refused:
                return Result(ok=False, op=op, error="simulated refusal")
            self._circuit.on_failure()
            return Result(ok=False, op=op, error="simulated failure")

        self._circuit.on_success()

        data: dict[str, Any] = {"simulated": True}
        if op == "llm_chat":
            data = {
                "id": "chatcmpl-fake",
                "object": "chat.completion",
                "choices": [{"message": {"role": "assistant", "content": "Simulated reply"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            }
        elif op == "llm_messages":
            data = {
                "id": "msg-fake",
                "type": "message",
                "content": [{"type": "text", "text": "Simulated Anthropic reply"}],
                "usage": {"input_tokens": 10, "output_tokens": 20},
            }
        elif op == "pool_status":
            data = {
                "total_providers": 34,
                "configured_keys": 5,
                "active_keys": 5,
                "cooldown_keys": 0,
                "combined_monthly_tokens_estimate": 7_400_000_000,
            }
        elif op == "rotate_key":
            data = {"provider": payload.get("provider", "groq"), "rotated_key": "sk-...test"}
        elif op == "test_provider":
            data = {"provider": payload.get("provider", "groq"), "reachable": True, "latency_ms": 35.0}

        res = Result(ok=True, op=op, data=data, duration_ms=10.0, attempts=1)
        self._idem.save(idem_key, res, klass=idem_class)
        return res

    def rollback(self, receipt_ref: str) -> Result:
        return Result(ok=True, op="rollback", data={"ref": receipt_ref})
