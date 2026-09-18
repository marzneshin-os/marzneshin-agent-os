"""Fake Adapter for OmniRoute LLM Gateway.

Must pass the same contract test as the real adapter.
"""

from __future__ import annotations

import json
from datetime import datetime

from adapters.base import Adapter, AdapterRefused, CircuitBreaker, Health, IdemClass, IdempotencyStore, Result, deadline_remaining_s


class OmniRouteFake(Adapter):
    name = "omniroute"

    def __init__(self, world_state=None, *, seed: int = 0, world: str = "sim"):
        self.world = world
        self._w = world_state
        self._circuit = CircuitBreaker()
        self._idem = IdempotencyStore()
        
        # Fault injection
        self.fail_healthz = False
        self.fail_next_execute = False
        self.fail_as_refused = False

    def healthz(self) -> Health:
        if self.fail_healthz:
            return Health(ok=False, detail="Injected failure", latency_ms=1.5)
        return Health(ok=True, detail="simulated ok", latency_ms=10.0)

    def capabilities(self) -> list[str]:
        return ["llm_chat"]

    def execute(self, op: str, payload: dict, *,
                idem_key: str, idem_class: IdemClass,
                dry_run: bool, deadline: datetime,
                provenance: list[dict]) -> Result:
        
        if op not in self.capabilities():
            return Result(ok=False, op=op, error=f"unknown op: {op}")

        stored = self._idem.lookup(idem_key)
        if stored:
            return stored

        if dry_run:
            res = Result(ok=True, op=op, dry_run=True, data={"choices": [{"message": {"content": "dry_run"}}]})
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
        
        res = Result(ok=True, op=op, data={
            "id": "chatcmpl-fake",
            "choices": [{"message": {"role": "assistant", "content": "Simulated reply"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        }, duration_ms=150.0)

        self._idem.save(idem_key, res, klass=idem_class)
        return res

    def rollback(self, receipt_ref: str) -> Result:
        return Result(ok=True, op="rollback", data={"ref": receipt_ref})
