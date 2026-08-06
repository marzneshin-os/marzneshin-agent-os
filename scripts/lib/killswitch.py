"""Kill switch — five independent paths, fail-closed (GAP G3, ADR-001 D5).

v1.0 put emergency stop behind a ClickUp task status: a paid external SaaS
reachable only with an expirable token. Three ways that gets you killed:
the token expires, the API is down, or the read fails and the naive
implementation assumes False and keeps going. That last one is fail-OPEN and
it is the worst failure mode a control system can have.

So:

  Activation (OR — any single path is sufficient to stop the system)
    K1  state/KILL file in the repo          local, atomic, versioned
    K2  GitHub repository variable            survives repo checkout loss
    K3  Moxt Workflow "Kill Switch" task      human-facing, no CLI needed
    K4  scripts/killswitch.py CLI             works with no network at all
    K5  automatic, by the Orchestrator        SLO breach, cost spike, anomaly

  Fail-closed rule
    If NO path yields a verdict with a timestamp fresher than
    FRESHNESS_LIMIT, every operation with blast radius above L3 halts.
    "I don't know" is equivalent to "stop", never to "permitted".

K1 is authoritative for reads because it is the only path with no external
dependency. K2/K3 are pulled into K1 by the heartbeat workflow, which is also
what keeps K1's timestamp fresh. That indirection is deliberate: it means a
worker deep in a task never needs network access to answer "am I allowed to
act?", which is what keeps the check inside the hook time budget (G9).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from . import clock, paths
from .atomic import CorruptState, read_json, write_json_atomic

SCHEMA_VERSION = "2.0.0"

# How stale a kill-switch verdict may be before we stop trusting it.
FRESHNESS_LIMIT_SECONDS = 15 * 60

# Operations at or below this autonomy level continue even when the kill
# switch state is unknown. L4/L3 are read and internal-artifact work: they
# cannot hurt a user or spend money.
UNKNOWN_STATE_MAX_LEVEL = 3


class Scope(str, Enum):
    GLOBAL = "global"
    AGENT = "agent"
    CAPABILITY = "capability"
    BUDGET = "budget"
    WORKSTREAM = "workstream"


class Verdict(str, Enum):
    RUNNING = "running"      # explicitly clear to operate
    KILLED = "killed"        # a matching kill is engaged
    UNKNOWN = "unknown"      # no fresh source -> fail closed


@dataclass
class KillEntry:
    scope: str
    target: str | None
    reason: str
    engaged_at: str
    engaged_by: str
    source: str  # K1..K5
    expires_at: str | None = None

    def matches(self, *, agent: str | None, capability: str | None,
                workstream: str | None) -> bool:
        if self.scope == Scope.GLOBAL.value:
            return True
        if self.scope == Scope.BUDGET.value:
            return True  # budget exhaustion stops all spending work
        if self.scope == Scope.AGENT.value:
            return bool(agent) and self._target_match(agent)
        if self.scope == Scope.CAPABILITY.value:
            return bool(capability) and self._target_match(capability)
        if self.scope == Scope.WORKSTREAM.value:
            return bool(workstream) and self._target_match(workstream)
        # Unknown scope string: treat as global. Fail closed on our own bugs too.
        return True

    def _target_match(self, value: str) -> bool:
        if not self.target:
            return True
        if self.target.endswith("*"):
            return value.startswith(self.target[:-1])
        return value == self.target

    def active(self) -> bool:
        if not self.expires_at:
            return True
        return clock.age_seconds(self.expires_at) < 0

    def to_dict(self) -> dict:
        d = {"scope": self.scope, "target": self.target, "reason": self.reason,
             "engaged_at": self.engaged_at, "engaged_by": self.engaged_by, "source": self.source}
        if self.expires_at:
            d["expires_at"] = self.expires_at
        return d


@dataclass
class KillState:
    verdict: Verdict
    entries: list[KillEntry] = field(default_factory=list)
    checked_at: str = ""
    freshness_seconds: float | None = None
    sources_consulted: list[str] = field(default_factory=list)
    detail: str = ""

    @property
    def killed(self) -> bool:
        return self.verdict is Verdict.KILLED

    def allows(self, autonomy_level: int) -> bool:
        """Whether an operation at this autonomy level may proceed.

        L0 is the most privileged class in BUILD-SPEC's numbering (L0 =
        proposal-only for pricing, L1 = money/infra with approval, L4 = read).
        Blast radius therefore *decreases* as the number rises, which is why
        the unknown-state gate is expressed as a minimum level.
        """
        if self.verdict is Verdict.RUNNING:
            return True
        if self.verdict is Verdict.KILLED:
            return False
        return autonomy_level >= UNKNOWN_STATE_MAX_LEVEL

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict.value,
            "killed": self.killed,
            "checked_at": self.checked_at,
            "freshness_seconds": self.freshness_seconds,
            "sources_consulted": self.sources_consulted,
            "entries": [e.to_dict() for e in self.entries],
            "detail": self.detail,
        }


def _read_k1() -> tuple[list[KillEntry], str | None, str]:
    """K1: state/KILL. Returns (entries, last_verified_at, note).

    Absence of the file is a *positive* statement that nothing is killed, but
    only if we can also establish freshness — which comes from the sidecar
    heartbeat file. A missing KILL file with no heartbeat is UNKNOWN, not
    RUNNING: on a fresh clone we must not assume the system is cleared to run.
    """
    kill_path = paths.kill_file()
    beat_path = paths.state_dir() / "KILL.heartbeat.json"

    entries: list[KillEntry] = []
    note = ""
    if kill_path.exists():
        try:
            data = read_json(kill_path, default={})
        except CorruptState:
            # Unparseable kill file: assume the worst.
            return ([KillEntry(scope=Scope.GLOBAL.value, target=None,
                               reason="state/KILL is corrupt and cannot be parsed",
                               engaged_at=clock.iso(), engaged_by="system:failclosed",
                               source="K1")], clock.iso(), "corrupt-kill-file")
        for raw in data.get("entries", []):
            entry = KillEntry(
                scope=raw.get("scope", Scope.GLOBAL.value),
                target=raw.get("target"),
                reason=raw.get("reason", ""),
                engaged_at=raw.get("engaged_at", clock.iso()),
                engaged_by=raw.get("engaged_by", "unknown"),
                source=raw.get("source", "K1"),
                expires_at=raw.get("expires_at"),
            )
            if entry.active():
                entries.append(entry)
        note = "kill-file-present"

    verified_at = None
    if beat_path.exists():
        try:
            beat = read_json(beat_path, default={})
            verified_at = beat.get("verified_at")
        except CorruptState:
            verified_at = None
    elif entries:
        # An engaged kill needs no freshness proof: it is already a stop.
        verified_at = clock.iso()

    return entries, verified_at, note


def _read_k2() -> tuple[list[KillEntry], str | None]:
    """K2: environment-injected repository variable.

    CI sets KILL_SWITCH from a GitHub repository variable. Reading an env var
    costs nothing and needs no network, so this path is always consulted.
    Format: "global" | "agent:lifecycle-growth" | "capability:cfg.publish.*"
    """
    raw = (os.environ.get("KILL_SWITCH") or "").strip()
    if not raw or raw.lower() in {"0", "false", "off", "none", "running"}:
        return [], None
    scope, _, target = raw.partition(":")
    scope = scope.strip().lower() or Scope.GLOBAL.value
    if scope in {"1", "true", "on", "killed"}:
        scope, target = Scope.GLOBAL.value, ""
    return ([KillEntry(scope=scope, target=target.strip() or None,
                       reason="KILL_SWITCH environment/repository variable",
                       engaged_at=clock.iso(), engaged_by="ci:repository-variable",
                       source="K2")], clock.iso())


def read_state() -> KillState:
    """Resolve the kill-switch verdict from all locally-available paths.

    K3 (Moxt Workflow) and K5 (Orchestrator automatic) are not polled here:
    they write into K1 via the heartbeat workflow. That keeps this function
    network-free and therefore usable inside a <3s hook.
    """
    consulted: list[str] = []
    entries: list[KillEntry] = []
    freshest: str | None = None

    k1_entries, k1_at, k1_note = _read_k1()
    consulted.append("K1:state/KILL")
    entries.extend(k1_entries)
    freshest = k1_at

    k2_entries, k2_at = _read_k2()
    consulted.append("K2:env/KILL_SWITCH")
    entries.extend(k2_entries)
    if k2_at and (not freshest or clock.parse_iso(k2_at) > clock.parse_iso(freshest)):
        freshest = k2_at

    checked_at = clock.iso()

    if entries:
        return KillState(verdict=Verdict.KILLED, entries=entries, checked_at=checked_at,
                         freshness_seconds=0.0, sources_consulted=consulted,
                         detail=f"{len(entries)} active kill entry/entries")

    if not freshest:
        return KillState(verdict=Verdict.UNKNOWN, checked_at=checked_at,
                         sources_consulted=consulted,
                         detail="no kill-switch source produced a verdict "
                                f"({k1_note or 'no kill file, no heartbeat'}); failing closed")

    age = clock.age_seconds(freshest)
    if age > FRESHNESS_LIMIT_SECONDS:
        return KillState(verdict=Verdict.UNKNOWN, checked_at=checked_at,
                         freshness_seconds=age, sources_consulted=consulted,
                         detail=f"newest verdict is {int(age)}s old, limit is "
                                f"{FRESHNESS_LIMIT_SECONDS}s; failing closed")

    return KillState(verdict=Verdict.RUNNING, checked_at=checked_at, freshness_seconds=age,
                     sources_consulted=consulted, detail="all sources clear")


def check(*, agent: str | None = None, capability: str | None = None,
          workstream: str | None = None, autonomy_level: int = 2) -> KillState:
    """Scoped check for one intended operation.

    Filters to entries that actually match this operation, so a kill scoped to
    one agent does not stop the whole fleet.
    """
    state = read_state()
    if state.verdict is not Verdict.KILLED:
        return state
    matching = [e for e in state.entries
                if e.matches(agent=agent, capability=capability, workstream=workstream)]
    if not matching:
        return KillState(verdict=Verdict.RUNNING, entries=[], checked_at=state.checked_at,
                         freshness_seconds=state.freshness_seconds,
                         sources_consulted=state.sources_consulted,
                         detail="kill entries exist but none match this scope")
    return KillState(verdict=Verdict.KILLED, entries=matching, checked_at=state.checked_at,
                     freshness_seconds=0.0, sources_consulted=state.sources_consulted,
                     detail="; ".join(e.reason for e in matching))


def engage(scope: str, *, target: str | None = None, reason: str,
           engaged_by: str, expires_at: str | None = None, source: str = "K4") -> KillState:
    """Engage a kill. Idempotent for an identical (scope, target) pair."""
    kill_path = paths.kill_file()
    try:
        data = read_json(kill_path, default={"schema_version": SCHEMA_VERSION, "entries": []})
    except CorruptState:
        data = {"schema_version": SCHEMA_VERSION, "entries": []}
    entry = KillEntry(scope=scope, target=target, reason=reason, engaged_at=clock.iso(),
                      engaged_by=engaged_by, source=source, expires_at=expires_at)
    kept = [e for e in data.get("entries", [])
            if not (e.get("scope") == scope and e.get("target") == target)]
    kept.append(entry.to_dict())
    data["entries"] = kept
    data["updated_at"] = clock.iso()
    write_json_atomic(kill_path, data)
    touch_heartbeat(verified_by=engaged_by, sources=["K4"])
    return read_state()


def release(scope: str, *, target: str | None = None, released_by: str) -> KillState:
    """Release one kill entry. Releasing a kill you did not engage is allowed
    (the Owner must always be able to clear anything) but it is recorded."""
    kill_path = paths.kill_file()
    try:
        data = read_json(kill_path, default={"schema_version": SCHEMA_VERSION, "entries": []})
    except CorruptState:
        data = {"schema_version": SCHEMA_VERSION, "entries": []}
    before = len(data.get("entries", []))
    data["entries"] = [e for e in data.get("entries", [])
                       if not (e.get("scope") == scope and e.get("target") == target)]
    data["updated_at"] = clock.iso()
    data.setdefault("release_log", []).append(
        {"scope": scope, "target": target, "released_by": released_by,
         "released_at": clock.iso(), "removed": before - len(data["entries"])})
    write_json_atomic(kill_path, data)
    touch_heartbeat(verified_by=released_by, sources=["K4"])
    return read_state()


def reconcile(*, external: list[KillEntry], sources: list[str], verified_by: str,
              prune_sources: list[str] | None = None) -> KillState:
    """Fold verdicts from the network-bound paths (K2/K3/K5) into K1.

    This is what lets a worker answer "am I allowed to act?" from a local file
    alone (ADR-002 D15): the heartbeat workflow polls the remote paths, calls
    this, and the freshness timestamp it stamps is what distinguishes a quiet
    system from an unmonitored one.

    `prune_sources` drops previously-reconciled entries from those sources
    before adding the current ones. Without it, a kill released remotely would
    live forever in K1 and the only way to clear it would be hand-editing the
    file that is meant to be authoritative.
    """
    kill_path = paths.kill_file()
    try:
        data = read_json(kill_path, default={"schema_version": SCHEMA_VERSION, "entries": []})
    except CorruptState:
        data = {"schema_version": SCHEMA_VERSION, "entries": []}

    prune = set(prune_sources or [])
    kept = [e for e in data.get("entries", []) if e.get("source") not in prune]
    kept.extend(e.to_dict() for e in external)
    data["entries"] = kept
    data["updated_at"] = clock.iso()
    data["reconciled_from"] = sources
    write_json_atomic(kill_path, data)
    touch_heartbeat(verified_by=verified_by, sources=sources,
                    extra={"reconciled_entries": len(external)})
    return read_state()


def touch_heartbeat(*, verified_by: str, sources: list[str],
                    extra: dict[str, Any] | None = None) -> None:
    """Record that the kill-switch state was verified against live sources.

    The heartbeat workflow calls this after successfully polling K2/K3. Its
    timestamp is what makes a *quiet* system (no KILL file) distinguishable
    from an *unmonitored* one. Without it we cannot tell "nothing is wrong"
    from "nobody has checked in three days".
    """
    payload = {"verified_at": clock.iso(), "verified_by": verified_by, "sources": sources}
    if extra:
        payload.update(extra)
    write_json_atomic(paths.state_dir() / "KILL.heartbeat.json", payload)
