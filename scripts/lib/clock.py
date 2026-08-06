"""Injectable clock. The single source of 'now' for the whole system.

Why this exists (ADR-001 D6): the simulation harness must run 72 simulated
hours in under 60 seconds, and every failure must be exactly reproducible from
a seed. That is impossible if any module calls datetime.now() directly.

RULE: no module outside this file may call time.time(), datetime.now(), or
random.*. `scripts/verify.py --lint-clock` enforces this in CI.
"""

from __future__ import annotations

import os
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...
    def monotonic_ms(self) -> int: ...
    def sleep(self, seconds: float) -> None: ...
    def rng(self) -> random.Random: ...


class RealClock:
    """Wall-clock. Used in production paths."""

    kind = "real"

    def __init__(self, seed: int | None = None) -> None:
        # Even in production we keep a seeded RNG so jitter is reproducible
        # when a receipt records the seed.
        self.seed = seed if seed is not None else int(time.time_ns() % (2**31))
        self._rng = random.Random(self.seed)

    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def monotonic_ms(self) -> int:
        return int(time.monotonic() * 1000)

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def rng(self) -> random.Random:
        return self._rng


class VirtualClock:
    """Deterministic clock for sim/ and tests.

    Time only advances when someone calls advance() or sleep(). sleep() is
    instant, which is what compresses 72h into <60s.
    """

    kind = "virtual"

    def __init__(self, start: datetime | None = None, seed: int = 1337) -> None:
        self._t = start or datetime(2026, 1, 1, tzinfo=timezone.utc)
        self._mono = 0
        self.seed = seed
        self._rng = random.Random(seed)
        self.slept_seconds = 0.0

    def now(self) -> datetime:
        return self._t

    def monotonic_ms(self) -> int:
        return self._mono

    def sleep(self, seconds: float) -> None:
        self.slept_seconds += seconds
        self.advance(seconds=seconds)

    def advance(self, seconds: float = 0, minutes: float = 0, hours: float = 0) -> datetime:
        delta = timedelta(seconds=seconds, minutes=minutes, hours=hours)
        self._t += delta
        self._mono += int(delta.total_seconds() * 1000)
        return self._t

    def rng(self) -> random.Random:
        return self._rng


_ACTIVE: Clock | None = None


def get_clock() -> Clock:
    """Process-wide clock.

    Honours MARZNESHIN_SIM_SEED so a CI job can replay a failed sim run
    without code changes.
    """
    global _ACTIVE
    if _ACTIVE is None:
        seed_env = os.environ.get("MARZNESHIN_SIM_SEED")
        if os.environ.get("MARZNESHIN_VIRTUAL_CLOCK") == "1":
            _ACTIVE = VirtualClock(seed=int(seed_env or 1337))
        else:
            _ACTIVE = RealClock(seed=int(seed_env) if seed_env else None)
    return _ACTIVE


def set_clock(clock: Clock | None) -> None:
    """Install a clock. Tests and sim/ call this; production never does."""
    global _ACTIVE
    _ACTIVE = clock


def now() -> datetime:
    return get_clock().now()


def iso() -> str:
    """ISO8601 UTC with 'Z', millisecond precision. The only timestamp format
    written anywhere in this system."""
    return to_iso(now())


def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def parse_iso(value: str) -> datetime:
    """Tolerant ISO8601 parse. Accepts 'Z', offsets, and missing fractions."""
    v = value.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def age_seconds(value: str | datetime) -> float:
    """Seconds elapsed since `value`. Negative if it is in the future."""
    dt = parse_iso(value) if isinstance(value, str) else value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now() - dt).total_seconds()
