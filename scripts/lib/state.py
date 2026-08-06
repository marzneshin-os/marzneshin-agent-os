"""STATE.json — the compacted snapshot (BUILD-SPEC §3.1).

STATE.json is a *derived* artifact. Events are the truth; this is a cache that
exists so a fresh session can orient in one read instead of replaying the log.
Two consequences that the code enforces:

  1. Every write is fenced. A stalled worker cannot overwrite the snapshot with
     a view of the world from before it was reassigned (see leases.py).
  2. It can always be rebuilt. scripts/compact.py regenerates it from events,
     and the cold-restore drill (§11.2) proves that regeneration is faithful.

`staleness` is a first-class concept here: SessionStart fails when the snapshot
is older than 24h and a sync cannot fix it (§7.2), because acting on a stale
world model is how autonomous systems cause damage confidently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import clock, leases, paths
from .atomic import CorruptState, read_json, write_json_atomic

SCHEMA_VERSION = "2.0.0"  # ADR-002 D11: aligned with BUILD-SPEC §3
STALENESS_LIMIT_SECONDS = 24 * 3600

HEALTH_VALUES = ("green", "amber", "red", "unknown")


class StateError(RuntimeError):
    pass


def empty(phase: str = "P0-bootstrap", active_slice: str = "VS-1") -> dict:
    """The zero state. Written once at bootstrap, then only ever compacted."""
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": clock.iso(),
        "generated_by": "bootstrap",
        "compacted_from_events": 0,
        "compacted_event_hash": None,
        "phase": phase,
        "active_slice": active_slice,
        "workstreams": {},
        "kpis": {},
        "kill_switch": {"global": False, "scoped": [], "verdict": "unknown"},
        "open_risks": [],
        "budget": {"tokens_spent_today": 0, "usd_spent_today": 0.0, "day": clock.now().date().isoformat()},
        "sense_level": "Tick-A",
        "open_tasks": [],
    }


def read() -> dict:
    path = paths.state_file()
    if not path.exists():
        raise StateError(
            f"{paths.rel(path)} does not exist. Run scripts/fsp.py bootstrap first."
        )
    try:
        return read_json(path, default=None)
    except CorruptState as exc:
        # Fail closed: a corrupt snapshot must not degrade to an empty one,
        # or a worker would happily act as if no work were in flight.
        raise StateError(
            f"STATE.json is corrupt ({exc}). Do NOT act on guessed state. "
            f"Rebuild with: python3 scripts/compact.py --rebuild"
        ) from exc


def read_or_empty() -> dict:
    try:
        return read()
    except StateError:
        return empty()


def age_seconds() -> float:
    return clock.age_seconds(read()["generated_at"])


def is_stale(limit_seconds: int = STALENESS_LIMIT_SECONDS) -> bool:
    try:
        return age_seconds() > limit_seconds
    except StateError:
        return True


def write(state: dict, *, holder: str | None = None, fencing_token: int | None = None,
          workstream: str | None = None) -> None:
    """Persist the snapshot.

    When a workstream is named, the write is fenced against that workstream's
    lease. Unfenced writes are permitted only for the compactor and bootstrap,
    which pass workstream=None deliberately.
    """
    if workstream:
        if holder is None or fencing_token is None:
            raise StateError("fenced write requires both holder and fencing_token")
        leases.assert_writable(workstream, holder, fencing_token)
    state["generated_at"] = clock.iso()
    state.setdefault("schema_version", SCHEMA_VERSION)
    write_json_atomic(paths.state_file(), state)


@dataclass
class WorkstreamView:
    name: str
    owner_agent: str = "orchestrator"
    open_tasks: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    last_receipt: str | None = None
    health: str = "unknown"
    lease: dict | None = None

    def to_dict(self) -> dict:
        return {"owner_agent": self.owner_agent, "open_tasks": self.open_tasks,
                "blocked_by": self.blocked_by, "last_receipt": self.last_receipt,
                "health": self.health, "lease": self.lease}


def upsert_workstream(state: dict, name: str, **fields: Any) -> dict:
    """Merge fields into a workstream entry, creating it if absent."""
    ws = state.setdefault("workstreams", {}).setdefault(
        name, WorkstreamView(name=name).to_dict())
    for key, value in fields.items():
        if key == "health" and value not in HEALTH_VALUES:
            raise StateError(f"health must be one of {HEALTH_VALUES}, got {value!r}")
        ws[key] = value
    return ws


def sync_leases(state: dict) -> dict:
    """Refresh the lease view from state/locks/.

    STATE.json mirrors leases for readability; the lock files are authoritative.
    Zombie leases are surfaced rather than silently dropped so the Handoff
    Guardian has something to act on.
    """
    live = {l.workstream: l.to_dict() for l in leases.list_all()}
    for name, ws in state.get("workstreams", {}).items():
        ws["lease"] = live.get(name)
    zombies = leases.find_zombies()
    if zombies:
        state["zombie_leases"] = zombies
    else:
        state.pop("zombie_leases", None)
    return state


def set_kpi(state: dict, name: str, value: Any) -> dict:
    state.setdefault("kpis", {})[name] = value
    return state


def add_risk(state: dict, *, id: str, severity: str, owner: str, note: str = "") -> dict:
    risks = state.setdefault("open_risks", [])
    for r in risks:
        if r.get("id") == id:
            r.update({"severity": severity, "owner": owner, "note": note,
                      "updated_at": clock.iso()})
            return state
    risks.append({"id": id, "severity": severity, "owner": owner, "note": note,
                  "opened_at": clock.iso()})
    return state


def summarize(state: dict | None = None) -> str:
    """One-screen human summary, used by HANDOFF.md and CONTEXT-PACK.md."""
    s = state or read_or_empty()
    lines = [
        f"phase={s.get('phase')} slice={s.get('active_slice')} sense={s.get('sense_level')}",
        f"snapshot_age={int(clock.age_seconds(s.get('generated_at', clock.iso())))}s "
        f"from {s.get('compacted_from_events', 0)} events",
    ]
    ks = s.get("kill_switch", {})
    lines.append(f"kill_switch={ks.get('verdict', 'unknown')} global={ks.get('global')}")
    for name, ws in sorted(s.get("workstreams", {}).items()):
        lease = ws.get("lease")
        held = f"{lease['holder']}@token{lease['fencing_token']}" if lease else "free"
        lines.append(
            f"  {name}: health={ws.get('health')} lease={held} "
            f"open={len(ws.get('open_tasks', []))} blocked={len(ws.get('blocked_by', []))}"
        )
    if s.get("zombie_leases"):
        lines.append(f"  ZOMBIE LEASES: {len(s['zombie_leases'])} (reaper action required)")
    if s.get("kpis"):
        kpis = ", ".join(f"{k}={v}" for k, v in sorted(s["kpis"].items()))
        lines.append(f"  kpis: {kpis}")
    for r in s.get("open_risks", []):
        lines.append(f"  risk {r.get('id')} sev={r.get('severity')} owner={r.get('owner')}")
    return "\n".join(lines)
