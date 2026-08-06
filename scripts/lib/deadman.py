"""Dead-man switch (BUILD-SPEC §11.2, VS-4).

If the human Owner goes silent, the system degrades itself instead of
either (a) running unsupervised at full capability forever, or (b) freezing
solid. The spec is explicit and this module is its only implementation:

  silence > 72h   -> level 1 "hold_l1":   L1 capabilities queue + hold;
                                          L2/L3 work continues (safe-continue)
  silence > 14d   -> level 2 "read_only": only read-class operations (L4)

Presence is a fact in the event log, never a memory: the Owner (or the
escrowed successor) emits `owner.heartbeat`; this module reads the LAST such
event and derives the level from its age. "I don't know" fails closed the
same way the kill switch does: no heartbeat anywhere = treat as absent.

The enforcer (orchestrator tick in prod, DeadManSwitchActor in sim) calls
refresh() every cycle; workers call allows(level) before acting. State lives
in state/deadman.json — script-written, never hand-edited — and every level
transition emits deadman.engaged / deadman.escalated.
"""

from __future__ import annotations

from . import clock, events, paths
from .atomic import read_json, write_json_atomic

LEVEL_NORMAL = 0
LEVEL_HOLD_L1 = 1
LEVEL_READ_ONLY = 2

LEVEL_NAMES = {LEVEL_NORMAL: "normal", LEVEL_HOLD_L1: "hold_l1",
               LEVEL_READ_ONLY: "read_only"}

# §11.2 thresholds. In hours so the constant reads like the spec sentence.
OWNER_SILENCE_HOLD_H = 72
OWNER_SILENCE_READONLY_H = 24 * 14

_OWNER_ACTOR_PARTITION = "human-owner"


def deadman_file():
    return paths.state_dir() / "deadman.json"


def owner_last_seen(*, world: str | None = None):
    """Timestamp of the most recent owner.heartbeat ever recorded, or None.

    Scans every day-dir for the owner partition and takes the newest beat.
    A short lookback window would lose a beat older than the window and
    report a present owner as absent — the exact false-positive the 14-day
    escalation cannot afford. Day dirs are few (one per day with beats), so
    the full scan is cheap; only the owner's own partition file is read.
    """
    from .atomic import read_ndjson
    w = world or paths.current_world()
    events_root = paths.state_dir() / "events"
    if w == "sim":
        events_root = events_root / "sim"
    if not events_root.exists():
        return None
    newest = None
    for path in sorted(events_root.glob(f"*/{_OWNER_ACTOR_PARTITION}.ndjson")):
        for e in read_ndjson(path):
            if e.get("type") != "owner.heartbeat":
                continue
            ts = clock.parse_iso(e["ts"])
            if newest is None or ts > newest:
                newest = ts
    return newest


from typing import Any

def compute_level(now=None) -> tuple[int, Any]:
    """(level, last_seen). Pure derivation from the log — no stored opinion."""
    now = now or clock.now()
    last = owner_last_seen()
    if last is None:
        # No heartbeat at all: the owner has never been seen in this window.
        # Fail closed to the strictest level, same rule as the kill switch.
        return LEVEL_READ_ONLY, None
    silence_h = (now - last).total_seconds() / 3600.0
    if silence_h > OWNER_SILENCE_READONLY_H:
        return LEVEL_READ_ONLY, last
    if silence_h > OWNER_SILENCE_HOLD_H:
        return LEVEL_HOLD_L1, last
    return LEVEL_NORMAL, last


def allows(autonomy_level: int, *, now=None) -> bool:
    """Whether an operation at this autonomy level may execute now.

    Workers read the PUBLISHED gate state (state/deadman.json), exactly like
    they read state/KILL for the kill switch: one cheap local file, no
    recomputation in the hot path. Where no enforcer is deployed (no file),
    the gate does not exist and everything is allowed — a library that
    silently engages in every test and sim run would be a detector crying
    wolf.

    hold_l1:   L1 is queued+held (returns False); L2/L3 continue.
    read_only: only L4 (read-class) proceeds.
    """
    state = read_json(deadman_file(), default=None)
    if state is None:
        return True
    level = state.get("level", LEVEL_NORMAL)
    if level == LEVEL_NORMAL:
        return True
    if level == LEVEL_HOLD_L1:
        return autonomy_level >= 2
    return autonomy_level >= 4


def current_state() -> dict:
    return read_json(deadman_file(), default=None) or {
        "level": LEVEL_NORMAL, "engaged_at": None, "escalated_at": None,
        "last_owner_seen": None, "updated_at": None}


def refresh(*, actor: events.Actor | None = None) -> dict:
    """Recompute the level from the log, persist, and emit on transitions.

    Idempotent: calling it every tick costs one state write and no events
    unless the level actually moved.
    """
    actor = actor or events.Actor(kind="system", id="deadman")
    level, last = compute_level()
    prev = current_state()
    if level == prev.get("level", LEVEL_NORMAL) and \
            prev.get("last_owner_seen") == (clock.to_iso(last) if last else None):
        return prev

    now_iso = clock.iso()
    new = dict(prev)
    new["level"] = level
    new["last_owner_seen"] = clock.to_iso(last) if last else None
    new["updated_at"] = now_iso
    if level == LEVEL_HOLD_L1 and prev.get("level", LEVEL_NORMAL) < LEVEL_HOLD_L1:
        new["engaged_at"] = now_iso
    if level == LEVEL_READ_ONLY and prev.get("level", LEVEL_NORMAL) < LEVEL_READ_ONLY:
        new["escalated_at"] = now_iso
    if level == LEVEL_NORMAL:
        new["engaged_at"] = None
        new["escalated_at"] = None
    write_json_atomic(deadman_file(), new)

    if level > prev.get("level", LEVEL_NORMAL):
        etype = "deadman.escalated" if level == LEVEL_READ_ONLY else "deadman.engaged"
        events.emit(etype, actor, events.Subject(kind="killswitch", id="deadman"),
                    {"level": LEVEL_NAMES[level],
                     "silence_h": None if last is None else round(
                         (clock.now() - last).total_seconds() / 3600.0, 2),
                     "last_owner_seen": new["last_owner_seen"]},
                    trust="internal")
    elif level < prev.get("level", LEVEL_NORMAL):
        events.emit("deadman.engaged", actor,
                    events.Subject(kind="killswitch", id="deadman"),
                    {"level": LEVEL_NAMES[level], "recovered": True},
                    trust="internal")
    return new
