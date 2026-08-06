"""Repo-root resolution and canonical path helpers.

Every other module resolves paths through here. Never hardcode a path
elsewhere: the simulation harness (VS-2) relocates the whole tree into a
tmpdir and relies on MARZNESHIN_OPS_ROOT to redirect all I/O.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

ROOT_ENV = "MARZNESHIN_OPS_ROOT"

# Files that mark the repo root. CLAUDE.md alone is not enough (the workspace
# has other CLAUDE.md files); the state/ dir is the discriminator.
_MARKERS = ("BUILD-SPEC.md", "state")


def repo_root() -> Path:
    """Return the repo root.

    Resolution order:
      1. $MARZNESHIN_OPS_ROOT  (simulation / test override)
      2. walk up from this file looking for the marker set
    """
    override = os.environ.get(ROOT_ENV)
    if override:
        return Path(override).resolve()

    here = Path(__file__).resolve()
    for candidate in (here, *here.parents):
        if all((candidate / m).exists() for m in _MARKERS):
            return candidate
    # scripts/lib/paths.py -> scripts/lib -> scripts -> root
    return here.parents[2]


def _p(*parts: str) -> Path:
    return repo_root().joinpath(*parts)


# --- state plane -----------------------------------------------------------

def state_dir() -> Path:
    return _p("state")


def state_file() -> Path:
    return _p("state", "STATE.json")


def handoff_file() -> Path:
    return _p("state", "HANDOFF.md")


def kill_file() -> Path:
    """K1 kill-switch path (ADR-001 D5). Absence means 'not killed'."""
    return _p("state", "KILL")


WORLD_ENV = "MARZ_WORLD"
WORLDS = ("prod", "sim")


def current_world() -> str:
    """Resolve prod|sim from the environment (BUILD-SPEC §2.1, ADR-002 D14).

    The switch between production and simulation is an environment variable,
    never a code branch. An unrecognised value fails closed to 'sim': writing
    simulated data into the production partition corrupts every KPI derived
    from it, so when in doubt we contaminate the disposable side.
    """
    raw = (os.environ.get(WORLD_ENV) or "prod").strip().lower()
    return raw if raw in WORLDS else "sim"


def _resolve_day(on: date | None) -> date:
    """Today, but never silently under a virtual clock.

    paths/ sits at the root of the import DAG and must not import clock, so it
    cannot ask for simulated time. Defaulting to the wall-clock date while a
    virtual clock is active would scatter a 72-hour simulated run across one
    real directory. Callers in that world must pass `on` explicitly.
    """
    if on is not None:
        return on
    if os.environ.get("MARZNESHIN_VIRTUAL_CLOCK") == "1":
        raise ValueError(
            "a virtual clock is active but no date was passed. Pass the "
            "simulated date explicitly (clock.now().date()) — defaulting to the "
            "wall-clock day would write simulated events under the real date."
        )
    return date.today()  # clock-ok: only reachable with a real clock; _resolve_day raises under a virtual clock when no date is passed


def events_dir(on: date | None = None, *, world: str | None = None) -> Path:
    """Per-day event directory. Actor-partitioned inside (ADR-001 D4).

    Simulation events live under their own root so they can never be read as
    production history (§3.2, ADR-002 D14):
        prod -> state/events/{date}/
        sim  -> state/events/sim/{date}/
    """
    day = _resolve_day(on).isoformat()
    w = world or current_world()
    if w == "sim":
        return _p("state", "events", "sim", day)
    return _p("state", "events", day)


def event_file(actor_id: str, on: date | None = None, *, world: str | None = None) -> Path:
    """One writer per file => merge conflicts are structurally impossible."""
    return events_dir(on, world=world) / f"{_slug(actor_id)}.ndjson"


def event_watermarks_file() -> Path:
    """Durable per-actor actor_seq watermarks (ADR-002 D18).

    Scanning recent files alone made an agent idle for longer than the scan
    window restart its counter at 1, which detect_gaps then reported as a
    phantom gap. A detector that cries wolf gets switched off.
    """
    return _p("state", "events", "_watermarks.json")


def anomalies_file() -> Path:
    """ADR-cited registry of explained actor_seq anomalies (VS-4, ADR-006).

    Raw events are immutable (§3.2), so a historical seq collision cannot be
    edited away — only explained. This file is written exclusively by
    events.register_anomaly(); hand-editing it is the same class of offence
    as hand-editing the log.
    """
    return _p("state", "events", "_anomalies.json")


def locks_dir() -> Path:
    return _p("state", "locks")


def lock_file(workstream: str) -> Path:
    return locks_dir() / f"{_slug(workstream)}.lock.json"


def fencing_file() -> Path:
    """Monotonic fencing-token counter, repo-wide (BUILD-SPEC §3.6)."""
    return _p("state", "locks", "_fencing.json")


def a2a_inbox(agent_id: str) -> Path:
    """T1 git-transport inbox (ADR-001 D1)."""
    return _p("state", "a2a", "inbox", _slug(agent_id))


def a2a_outbox(agent_id: str) -> Path:
    return _p("state", "a2a", "outbox", _slug(agent_id))


def a2a_processed(agent_id: str) -> Path:
    """Archive: inbox files are never deleted, only moved here (§5.1, I17)."""
    return _p("state", "a2a", "processed", _slug(agent_id))


def a2a_idem_dir() -> Path:
    return _p("state", "a2a", "idem")


def a2a_t2_dir() -> Path:
    """T2 dispatch records: envelope <-> Moxt Workflow task mapping (§5.2)."""
    return _p("state", "a2a", "t2")


def a2a_t2_health_file() -> Path:
    return _p("state", "a2a", "t2", "health.json")


def transport_health_file() -> Path:
    return _p("state", "a2a", "transport_health.json")


def registry_file() -> Path:
    """Agent registry consumed by lib at runtime. JSON, not YAML: lib must
    stay stdlib-only (G9 / lint-imports), so no YAML parser may live here."""
    return _p("agents", "registry.json")


def archive_dir() -> Path:
    return _p("state", "archive")


# --- receipts / decisions / agents ----------------------------------------

def receipts_dir(on: date | None = None) -> Path:
    day = _resolve_day(on)  # virtual-clock safe: raises instead of scattering receipts under the wall-clock date
    return _p("receipts", f"{day.year:04d}", f"{day.month:02d}")


def receipt_file(task_id: str, on: date | None = None) -> Path:
    return receipts_dir(on) / f"{_slug(task_id)}.json"


def receipt_head_file(workstream: str) -> Path:
    """Head of the per-workstream receipt hash chain (G18)."""
    return _p("receipts", "_chain", f"{_slug(workstream)}.head.json")


def schemas_dir() -> Path:
    return _p("analytics", "schemas")


def schema_file(name: str) -> Path:
    return schemas_dir() / f"{name}.schema.json"


def agent_cards_dir() -> Path:
    return _p("agents", "cards")


def agent_card_file(agent_id: str) -> Path:
    return agent_cards_dir() / f"{_slug(agent_id)}.yaml"


def budget_ledger_file() -> Path:
    return _p("state", "budget", "ledger.ndjson")


def artifacts_dir() -> Path:
    return _p("artifacts")


def context_pack_file() -> Path:
    return _p("CONTEXT-PACK.md")


def tradeoff_register_file() -> Path:
    return _p("decisions", "TRADEOFF-REGISTER.md")


def _slug(value: str) -> str:
    """Filesystem-safe token. Keeps ids readable: 'agent:config-eng' -> 'agent-config-eng'."""
    out = []
    for ch in value.strip():
        if ch.isalnum() or ch in "-_.":
            out.append(ch)
        else:
            out.append("-")
    slug = "".join(out).strip("-")
    return slug or "unknown"


# Public alias: other modules need slugging for their own filenames.
slug = _slug


def ensure_parent(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def rel(path: Path | str) -> str:
    """Repo-relative POSIX path, for recording inside artifacts."""
    p = Path(path).resolve()
    try:
        return p.relative_to(repo_root()).as_posix()
    except ValueError:
        return p.as_posix()
