"""Marzneshin Autonomous OS — shared core library.

Import discipline (enforced by scripts/verify.py --lint-imports):

    paths      <- nothing
    clock      <- nothing
    ids        <- clock
    redact     <- nothing
    atomic     <- ids
    tokensaver <- nothing
    router     <- clock, paths, atomic, ids, tokensaver
    events     <- clock, paths, atomic, ids, redact
    leases     <- clock, paths, atomic
    killswitch <- clock, paths, atomic
    receipts   <- clock, paths, atomic, ids, redact
    policy     <- clock, killswitch, ids
    state      <- clock, paths, atomic, leases
    budget     <- clock, paths, atomic, ids
    validate   <- paths, atomic

No cycles. Nothing in here performs network I/O, so every module is safe to
call from a hook inside the 3-second budget (GAP G9). Adapters do the I/O and
live in adapters/, one layer out (BUILD-SPEC §4).
"""

from __future__ import annotations

from . import (atomic, budget, clock, events, ids, killswitch, leases, paths,
               policy, receipts, redact, router, state, tokensaver, validate)

__version__ = "2.0.0"

__all__ = [
    "atomic", "budget", "clock", "events", "ids", "killswitch",
    "leases", "paths", "policy", "receipts", "redact", "router",
    "state", "tokensaver", "validate",
]
