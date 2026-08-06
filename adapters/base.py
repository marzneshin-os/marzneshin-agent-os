"""Adapter Protocol — the contract between L2 execution and L0 systems (§4).

L2 (agents) never touches L0 (Marzneshin, payments, ...) directly; everything
goes through an Adapter. The protocol is deliberately small:

    healthz()      -> Health
    capabilities() -> list of operation names
    execute(op, payload, *, idem_key, idem_class, dry_run, deadline,
            provenance) -> Result
    rollback(receipt_ref) -> Result

Shared requirements (§4): idempotency per declared class · exponential
backoff with jitter · circuit breaker (5 consecutive errors -> open 60s) ·
hard timeout · redaction on logs · a REAL dry_run (not a no-op) · an
independent contract test · a matching fake in sim/fakes that passes the
SAME contract test. An adapter without a fake does not merge — without it the
§16 scenarios cannot run.

No module here does network I/O. Real adapters do I/O in their own module;
fakes live in sim/fakes; both are driven through this protocol.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Literal, Protocol

IdemClass = Literal["forever", "scoped", "none"]
World = Literal["prod", "sim"]


class AdapterError(RuntimeError):
    """Transport-level failure (timeout, 5xx, connection). Counted by the
    circuit breaker."""


class AdapterRefused(AdapterError):
    """The adapter refused the call (policy, validation, dry_run detected
    side effect)."""


@dataclass
class Health:
    ok: bool
    detail: str = ""
    latency_ms: float = 0.0

    def to_dict(self) -> dict:
        return {"ok": self.ok, "detail": self.detail, "latency_ms": self.latency_ms}


@dataclass
class Result:
    ok: bool
    op: str
    data: dict = field(default_factory=dict)
    error: str | None = None
    dry_run: bool = False
    replayed: bool = False        # True when idempotency returned a stored result
    attempts: int = 1
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {"ok": self.ok, "op": self.op, "data": self.data, "error": self.error,
                "dry_run": self.dry_run, "replayed": self.replayed,
                "attempts": self.attempts, "duration_ms": round(self.duration_ms, 1)}


class Adapter(Protocol):
    name: str
    world: World

    def healthz(self) -> Health: ...
    def capabilities(self) -> list[str]: ...
    def execute(self, op: str, payload: dict, *,
                idem_key: str, idem_class: IdemClass,
                dry_run: bool, deadline: datetime,
                provenance: list[dict]) -> Result: ...
    def rollback(self, receipt_ref: str) -> Result: ...


# --- shared machinery: idempotency store + circuit breaker ------------------

class CircuitOpen(AdapterError):
    """The breaker is open; calls fail fast instead of hammering a dead peer."""


class CircuitBreaker:
    """5 consecutive failures -> open for `reset_after_s` (§4).

    half-open after the cool-down: one probe call decides close vs re-open.
    """

    def __init__(self, *, threshold: int = 5, reset_after_s: float = 60.0) -> None:
        self.threshold = threshold
        self.reset_after_s = reset_after_s
        self.failures = 0
        self.opened_at: float | None = None

    def before_call(self) -> None:
        if self.opened_at is None:
            return
        elapsed = time.monotonic() - self.opened_at
        if elapsed < self.reset_after_s:
            raise CircuitOpen(
                f"circuit open ({self.failures} consecutive failures, "
                f"{int(self.reset_after_s - elapsed)}s until probe)")
        # half-open: allow one probe; failures counter resets only on success

    def on_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def on_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = time.monotonic()

    @property
    def state(self) -> str:
        if self.opened_at is None:
            return "closed"
        return "open" if time.monotonic() - self.opened_at < self.reset_after_s else "half-open"


class IdempotencyStore:
    """Result memo per idem class (§3.5/G4).

    forever -> repeat with same key returns the stored result, no re-execute
    scoped  -> same, but only within ttl_s
    none    -> never stored
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[float | None, Result]] = {}

    def lookup(self, key: str) -> Result | None:
        entry = self._store.get(key)
        if not entry:
            return None
        expires, result = entry
        if expires is not None and time.monotonic() > expires:
            del self._store[key]
            return None
        return Result(**{**result.to_dict(), "replayed": True})  # type: ignore[arg-type]

    def save(self, key: str, result: Result, *, klass: IdemClass, ttl_s: int = 900) -> None:
        if klass == "none":
            return
        expires = None if klass == "forever" else time.monotonic() + ttl_s
        self._store[key] = (expires, result)


def deadline_remaining_s(deadline: datetime) -> float:
    """Seconds until the hard deadline; <=0 means the caller is out of time.

    Routed through lib/clock (D6): under a VirtualClock the deadline lives in
    virtual time, so 'now' must too.
    """
    from lib import clock  # lazy: adapters always run with scripts/ on sys.path
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    return (deadline - clock.now()).total_seconds()


def backoff_delays(*, base_s: float = 0.25, factor: float = 2.0, attempts: int = 3,
                   jitter: float = 0.5, rng=None) -> list[float]:
    """Exponential backoff with jitter (§4). RNG injected for determinism;
    defaults to the active clock's seeded stream so production jitter is
    reproducible when the receipt records the seed (D6)."""
    if rng is None:
        from lib import clock  # lazy: see deadline_remaining_s
        rng = clock.get_clock().rng()
    delays = []
    for i in range(attempts):
        raw = base_s * (factor ** i)
        delays.append(raw + rng.uniform(0, raw * jitter))
    return delays
