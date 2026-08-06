#!/usr/bin/env python3
"""compact.py — rebuild STATE.json from the event log (BUILD-SPEC §3.1).

STATE.json is derived, never truth (I1 companion rule): this script is the
only writer besides bootstrap, and it can always regenerate the snapshot from
events + receipts + leases + budget. That property is what the cold-restore
drill (§11.2) measures.

    compact.py            compact recent events into STATE.json (hourly job)
    compact.py --rebuild  rebuild from ALL history (cold-restore path)
    compact.py --days N   lookback window for the default run (default 2)

The compactor also:
  - publishes actor_seq watermarks into compacted_from (ADR-002 D18)
  - runs detect_gaps and emits event.gap.detected for any loss found (§3.1)
  - syncs the lease view and surfaces zombies for the Handoff Guardian
  - refreshes receipt KPIs (coverage, crash_rate) and the budget summary
  - never rewrites a raw event: compaction writes snapshots, not history
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import budget, clock, events, killswitch, paths, receipts, state  # noqa: E402
from lib.atomic import read_json  # noqa: E402


def _watermarks() -> dict:
    return read_json(paths.event_watermarks_file(), default={}) or {}


def _receipt_views() -> dict:
    """Per-workstream chain view for STATE, from the receipt heads on disk."""
    views: dict[str, dict] = {}
    chain_dir = paths.repo_root() / "receipts" / "_chain"
    if chain_dir.exists():
        for f in sorted(chain_dir.glob("*.head.json")):
            head = read_json(f, default={}) or {}
            ws = f.name[: -len(".head.json")]
            views[ws] = {"receipt_chain_head": head.get("hash"),
                         "receipt_chain_length": head.get("count", 0),
                         "last_receipt": head.get("task_id")}
    return views


def compact(*, start: date, end: date, rebuild: bool = False,
            actor: events.Actor | None = None) -> dict:
    actor = actor or events.Actor(kind="system", id="compact")

    try:
        current = state.read()
    except state.StateError:
        current = state.empty()

    collected: list[dict] = list(events.iter_range(start, end, world="prod"))

    # Derive carried fields from the event stream itself (§3.1: STATE is
    # derived, never source). The cold-restore drill (VS-4) caught that a
    # from-scratch rebuild lost phase/slice (bootstrap-only), owner_agent
    # (claim-only) and health (reaper-only) because compaction merely merged
    # yesterday's STATE forward. Derivation rule: latest event in the window
    # wins; fields not re-derived in this window keep their carried value.
    derived_ws: dict[str, dict] = {}
    for ev in sorted(collected, key=lambda e: e.get("ts", "")):
        etype = ev.get("type")
        payload = ev.get("payload") or {}
        subject = ev.get("subject") or {}
        if etype == "session.started":
            if payload.get("phase"):
                current["phase"] = payload["phase"]
            if payload.get("slice"):
                current["active_slice"] = payload["slice"]
        elif etype == "slice.transitioned":
            # ADR-008. session.started only reports where a session *opened*;
            # this carries a change made mid-phase. Both are handled in the same
            # ts-ordered pass, so whichever happened last wins — which is why a
            # transition emitted after a session start correctly supersedes it.
            # The subject is authoritative for the slice (payload.to is the
            # human-readable echo of it).
            to_slice = subject.get("id") or payload.get("to")
            if to_slice:
                current["active_slice"] = to_slice
            if payload.get("phase"):
                current["phase"] = payload["phase"]
        elif etype == "lease.acquired" and subject.get("kind") == "workstream":
            ws = derived_ws.setdefault(subject.get("id", ""), {})
            if ev.get("actor", {}).get("id"):
                ws["owner_agent"] = ev["actor"]["id"]
            ws["health"] = "unknown"  # a live lease supersedes a past crash
        elif etype in ("task.crashed", "lease.revoked"):
            ws_name = payload.get("workstream") or (
                subject.get("id") if subject.get("kind") == "workstream" else None)
            if ws_name:
                derived_ws.setdefault(ws_name, {})["health"] = "red"
    for ws_name, fields in derived_ws.items():
        if ws_name:
            state.upsert_workstream(current, ws_name, **fields)

    # KPIs that the loop reads at Tick-A (§12.0): repo health, receipts, cost.
    rstats = receipts.stats()
    coverage = 1.0 if rstats["total"] or not current.get("open_tasks") else 0.0
    state.set_kpi(current, "receipt_coverage", coverage)
    # ADR-007: crash_rate is the trailing-window figure the budget judges. The
    # lifetime figure and the sample size ship alongside it so an agent reading
    # only STATE.json cannot mistake a short window for a clean history.
    state.set_kpi(current, "crash_rate", rstats["crash_rate"])
    state.set_kpi(current, "crash_rate_lifetime", rstats["crash_rate_lifetime"])
    state.set_kpi(current, "crash_rate_window", rstats["window_size"])
    state.set_kpi(current, "crash_rate_sample_sufficient", rstats["sample_sufficient"])
    state.set_kpi(current, "receipts_total", rstats["total"])

    ws_budget = budget.status("workspace")
    current["budget"] = {
        "day": ws_budget["day"],
        "tokens_spent_today": ws_budget["spent"]["tokens"],
        "usd_spent_today": ws_budget["spent"]["usd"],
        "utilization": ws_budget["utilization"],
        "state": ("exhausted" if ws_budget["exhausted"]
                  else "escalated" if ws_budget["should_escalate"] else "normal"),
        "forecast": budget.forecast()["projected_eod"],
    }

    ks = killswitch.read_state()
    current["kill_switch"] = {
        "global": ks.killed and any(e.scope == "global" for e in ks.entries),
        "scoped": [f"{e.scope}:{e.target}" for e in ks.entries if e.scope != "global"],
        "verdict": ks.verdict.value,
        "read_from": ks.sources_consulted,
        "read_at": ks.checked_at,
        "freshness_s": ks.freshness_seconds,
        "fail_closed_engaged": ks.verdict is killswitch.Verdict.UNKNOWN,
    }

    # Workstream view: leases (authoritative) + receipt chain heads.
    for ws_name, view in _receipt_views().items():
        state.upsert_workstream(current, ws_name, **view)
    state.sync_leases(current)

    # Event-gap detection is part of compaction (§3.1): a gap in an actor's
    # sequence means an event was lost, and silent loss in an audit log is
    # worse than a red build.
    gaps = events.detect_gaps(start, end, world="prod")
    for gap in gaps:
        events.emit("event.gap.detected", actor,
                    events.Subject(kind="actor", id=gap["actor"]),
                    {"missing_seq": gap["missing_seq"], "duplicate_seq": gap["duplicate_seq"],
                     "range": gap["range"], "window": [start.isoformat(), end.isoformat()]})

    current["compacted_from_events"] = len(collected)
    current["compacted_event_hash"] = events.chain_hash(collected) if collected else None
    current["compacted_from"] = {
        "until_ts": clock.iso(),
        "event_count": len(collected),
        "event_hash": current["compacted_event_hash"],
        "actor_seq_watermarks": _watermarks(),
        "window": "full" if rebuild else [start.isoformat(), end.isoformat()],
    }
    current["generated_by"] = "compact.py --rebuild" if rebuild else "compact.py"

    # Unfenced write: the compactor and bootstrap are the only callers allowed
    # to write STATE.json without a workstream lease (lib/state.py docstring).
    state.write(current)
    events.emit("state.compacted", actor, events.Subject(kind="state", id="STATE.json"),
                {"event_count": len(collected), "rebuild": rebuild,
                 "gaps_detected": len(gaps), "world": "prod"})
    return current


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="compact.py",
                                     description="Rebuild STATE.json from the event log")
    parser.add_argument("--rebuild", action="store_true",
                        help="rebuild from all available history (cold-restore path)")
    parser.add_argument("--days", type=int, default=2,
                        help="lookback window for the default run")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    end = clock.now().date()
    if args.rebuild:
        # Find the oldest event day on disk; default to the window when empty.
        roots = [paths.events_dir(end - timedelta(days=d)) for d in range(0, 370)]
        existing = [r for r in roots if r.exists()]
        start = end - timedelta(days=364) if existing else end - timedelta(days=args.days)
        for d in range(0, 370):
            if paths.events_dir(end - timedelta(days=d)).exists():
                start = end - timedelta(days=d)
    else:
        start = end - timedelta(days=args.days)

    result = compact(start=start, end=end, rebuild=args.rebuild)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        print(state.summarize(result))
        print(f"\ncompacted: {result['compacted_from_events']} events "
              f"(window: {result['compacted_from']['window']})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"compact: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
