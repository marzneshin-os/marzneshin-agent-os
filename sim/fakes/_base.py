"""sim/fakes/_base.py — shared machinery for all fake adapters.

A fake is not a mock: it implements the SAME Adapter protocol, passes the
SAME contract suite (adapters/contract.py), and reads/writes the same World
its real counterpart would touch (§16: fake/real divergence = worthless sim).

Chaos hooks:
  set_down(bool)     the whole adapter is unreachable (gateway_down, ...)
  fail_next(n, err)  the next n calls raise AdapterError (flaky network, 5xx)
"""

from __future__ import annotations

from datetime import datetime

from adapters.base import (AdapterError, AdapterRefused, CircuitBreaker, Health,
                           IdempotencyStore, Result)


class FakeBase:
    name = "fake"
    world = "sim"
    OPS: list[str] = []

    def __init__(self, world_state, *, seed: int = 0) -> None:
        self._w = world_state
        self._idem = IdempotencyStore()
        self._breaker = CircuitBreaker()
        self._down = False
        self._fail_next: list[Exception] = []
        self.op_log: list[dict] = []

    # --- chaos hooks ---------------------------------------------------------
    def set_down(self, down: bool) -> None:
        self._down = down

    def fail_next(self, n: int, error: Exception | None = None) -> None:
        self._fail_next.extend([error or AdapterError(f"{self.name}: injected failure")] * n)

    # --- protocol -------------------------------------------------------------
    def healthz(self) -> Health:
        if self._down:
            return Health(ok=False, detail=f"{self.name} is down (chaos)")
        return Health(ok=True, detail="sim", latency_ms=0.5)

    def capabilities(self) -> list[str]:
        return list(self.OPS)

    def execute(self, op: str, payload: dict, *, idem_key: str, idem_class: str,
                dry_run: bool, deadline: datetime, provenance: list[dict]) -> Result:
        if op not in self.OPS:
            return Result(ok=False, op=op, error=f"unknown op {op!r} for {self.name}")
        self._breaker.before_call()
        if self._down:
            raise AdapterError(f"{self.name}: adapter unreachable (chaos down)")
        if self._fail_next:
            err = self._fail_next.pop(0)
            self._breaker.on_failure()
            raise err

        hit = self._idem.lookup(idem_key)
        if hit is not None:
            return hit

        try:
            data = self._apply(op, payload or {}, dry_run=dry_run,
                               provenance=provenance or [])
        except AdapterRefused as exc:
            result = Result(ok=False, op=op, error=str(exc), dry_run=dry_run)
            self._breaker.on_success()
            return result

        self._breaker.on_success()
        result = Result(ok=True, op=op, data=data, dry_run=dry_run)
        self._idem.save(idem_key, result, klass=idem_class)  # type: ignore[arg-type]
        self.op_log.append({"op": op, "dry_run": dry_run, "payload_keys": sorted(payload or {}),
                            "tick": getattr(self._w, "tick", None)})
        return result

    def rollback(self, receipt_ref: str) -> Result:
        return Result(ok=False, op="rollback",
                      error=f"{self.name}: no rollback handler for {receipt_ref}")

    # --- for subclasses ---------------------------------------------------------
    def _apply(self, op: str, payload: dict, *, dry_run: bool,
               provenance: list[dict]) -> dict:
        raise NotImplementedError
