#!/usr/bin/env python3
"""fsp.py — session protocol driver (BUILD-SPEC §0).

The nine-step protocol (SYNC → GAP SCAN → CLAIM → PLAN → SIM → EXECUTE →
VERIFY → EMIT → HANDOFF) is executed by the worker; this script provides the
steps that must be enforced by code rather than by discipline:

    fsp.py bootstrap                        first run on a fresh clone: zero
                                            STATE.json, dirs, HANDOFF skeleton
    fsp.py status                           one-screen SYNC readout
    fsp.py claim WORKSTREAM --agent A       step 3: lease + fencing token
              [--session S] [--ttl MIN]
    fsp.py heartbeat WORKSTREAM --agent A   keep the lease alive (15m SLA)
    fsp.py slice VS-N --agent A [--phase P] move the phase/slice pointer on the
              [--note WHY]                  log instead of by hand (ADR-008)
    fsp.py release WORKSTREAM --agent A     step 9's other half: free the lease

Every state-changing command emits its event (§3.2). Bootstrap is the only
command allowed to write STATE.json without a lease (state.py docstring).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import clock, events, leases, paths, state  # noqa: E402
from lib.atomic import write_text_atomic  # noqa: E402

HANDOFF_SKELETON = """# HANDOFF

> Last session state, human-readable. Rewritten at the end of every session
> (Iron Rule 3: no session ends without a HANDOFF). Machine state lives in
> STATE.json + the event log; this file is the orientation layer.

- **Updated:** {ts}
- **By:** {agent}
- **Slice:** VS-1 (Spine)

## Where we are

Bootstrap complete. No work in flight.

## Next

Run `python3 scripts/fsp.py status`, then read `decisions/GAP-REPORT-003.md`
for the current gap scan.

## Blockers

None recorded.
"""


def cmd_bootstrap(args) -> int:
    root = paths.repo_root()
    created: list[str] = []
    for rel in ("state/events/sim", "state/locks", "state/budget", "state/archive",
                "state/a2a/inbox", "state/a2a/outbox", "state/a2a/processed",
                "receipts", "artifacts", "decisions/ADR"):
        target = root / rel
        if not target.exists():
            target.mkdir(parents=True, exist_ok=True)
            created.append(rel + "/")

    if paths.state_file().exists() and not args.force:
        print("STATE.json already exists — bootstrap is idempotent, doing nothing.")
        print("Use --force to re-zero the snapshot (events and receipts are never touched).")
        return 0

    s = state.empty(phase=args.phase, active_slice=args.slice)
    state.write(s)  # unfenced: bootstrap is the permitted exception
    created.append("state/STATE.json")

    if not paths.handoff_file().exists():
        write_text_atomic(paths.handoff_file(),
                          HANDOFF_SKELETON.format(ts=clock.iso(), agent=args.agent))
        created.append("state/HANDOFF.md")

    actor = events.Actor(kind="system", id="bootstrap")
    events.emit("session.started", actor, events.Subject(kind="repo", id="marzneshin-ops"),
                {"phase": args.phase, "slice": args.slice, "by": args.agent,
                 "created": created})
    print(f"bootstrap complete: phase={args.phase} slice={args.slice}")
    for item in created:
        print(f"  + {item}")
    print("\nNext: python3 scripts/fsp.py claim <workstream> --agent <id>")
    return 0


def cmd_status(args) -> int:
    print(state.summarize())
    print()
    for lease in leases.list_all():
        flag = "ZOMBIE " if lease.expired() else ""
        print(f"{flag}lease {lease.workstream}: {lease.holder} "
              f"token={lease.fencing_token} expires={lease.expires_at}")
    zombies = leases.find_zombies()
    if zombies:
        print(f"\n{len(zombies)} zombie lease(s) — run scripts/reaper.py")
    return 0


def cmd_claim(args) -> int:
    session = args.session or f"S-{clock.now().strftime('%H%M%S')}"
    actor = events.Actor(kind="agent", id=args.agent, session=session)
    try:
        lease = leases.acquire(args.workstream, f"agent:{args.agent}", session,
                               ttl_min=args.ttl)
    except leases.LeaseHeld as exc:
        print(f"claim refused: {exc}", file=sys.stderr)
        return 1
    events.emit("lease.acquired", actor,
                events.Subject(kind="workstream", id=args.workstream),
                {"fencing_token": lease.fencing_token, "ttl_min": args.ttl})
    try:
        s = state.read()
        state.upsert_workstream(s, args.workstream, owner_agent=args.agent)
        state.sync_leases(s)
        state.write(s, holder=f"agent:{args.agent}",
                    fencing_token=lease.fencing_token, workstream=args.workstream)
    except state.StateError:
        pass  # STATE absent on a fresh clone; bootstrap covers it
    print(f"claimed {args.workstream}: fencing_token={lease.fencing_token} "
          f"ttl={args.ttl}m session={session}")
    print(f"export MARZ_AGENT_ID={args.agent} MARZ_WORKSTREAM={args.workstream} "
          f"MARZ_FENCING_TOKEN={lease.fencing_token} MARZ_SESSION={session}")
    return 0


def cmd_heartbeat(args) -> int:
    try:
        lease = leases.renew(args.workstream, f"agent:{args.agent}")
    except leases.LeaseError as exc:
        print(f"heartbeat failed: {exc}", file=sys.stderr)
        return 1
    events.emit("agent.heartbeat",
                events.Actor(kind="agent", id=args.agent, session=lease.session),
                events.Subject(kind="workstream", id=args.workstream),
                {"fencing_token": lease.fencing_token})
    print(f"heartbeat ok: {args.workstream} (holder {args.agent})")
    return 0


SLICE_WORKSTREAM = "agentic-core"


def cmd_slice(args) -> int:
    """Move the phase/slice pointer, on the log, under the lease (ADR-008).

    STATE.active_slice read VS-3 for three days while VS-4 was in progress.
    Compaction was not wrong: `slice` was only derivable from a
    `session.started` payload, so a slice change *mid-phase* had no event that
    could carry it. The tempting fix — open STATE.json and retype the value —
    is exactly what §3.1 forbids and what the pre-tool hook blocks, because a
    hand-edited snapshot can no longer be rebuilt from history.

    So the pointer moves the same way everything else does: emit an event, then
    let the compactor derive the snapshot from it.

    Fencing applies to narrative state too. The phase pointer is repo-global —
    letting an agent that does not hold the workstream move it would let a
    stalled worker rewrite everyone's sense of where the project is, which is
    the precise failure the lease exists to prevent.
    """
    ws = args.workstream
    holder = f"agent:{args.agent}"
    lease = leases.read(ws)

    # Fencing here is about *contention*, not ceremony. A lease held by someone
    # else must block the write — that is the stalled-worker case the lease
    # exists for. An unclaimed workstream has no conflicting owner and no token
    # to be stale against, so demanding a claim first would only make the
    # bootstrap path (and every drill that rebuilds from zero) impossible
    # without inventing a lease nobody needs.
    if lease is not None and lease.holder != holder and not lease.expired():
        print(f"slice refused: the {ws!r} lease is held by {lease.holder} "
              f"(token {lease.fencing_token}), not by {holder}. Narrative state "
              f"is fenced like every other write (BUILD-SPEC §3.1). Wait for the "
              f"holder to release it, or run scripts/reaper.py if it is a zombie.",
              file=sys.stderr)
        return 1
    mine = lease if (lease is not None and lease.holder == holder
                     and not lease.expired()) else None

    s = state.read_or_empty()
    from_slice = s.get("active_slice")
    from_phase = s.get("phase")
    to_phase = args.phase or from_phase

    if from_slice == args.slice and to_phase == from_phase:
        print(f"already at phase={to_phase} slice={args.slice} — nothing to do.")
        return 0

    actor = events.Actor(kind="agent", id=args.agent,
                         session=mine.session if mine else None)
    ev = events.emit("slice.transitioned", actor,
                     events.Subject(kind="slice", id=args.slice),
                     {"from": from_slice, "to": args.slice,
                      "from_phase": from_phase, "phase": to_phase,
                      "workstream": ws,
                      "fencing_token": mine.fencing_token if mine else None,
                      "note": args.note})

    # The event is the truth; the snapshot is a cache. Refresh the cache under
    # the fence so `status` is right immediately instead of only after the next
    # compaction — but compact.py derives the same values from the event alone,
    # which is what the cold-restore drill checks.
    s["active_slice"] = args.slice
    s["phase"] = to_phase
    try:
        if mine:
            state.write(s, holder=holder, fencing_token=mine.fencing_token,
                        workstream=ws)
        else:
            state.write(s)
    except (state.StateError, leases.LeaseError) as exc:
        print(f"slice: event {ev.event_id} recorded, but the snapshot write was "
              f"refused ({exc}). Run scripts/compact.py to rebuild.", file=sys.stderr)
        return 1

    print(f"slice {from_slice} -> {args.slice}"
          + (f"  phase {from_phase} -> {to_phase}" if to_phase != from_phase else "")
          + f"\nevent={ev.event_id}")
    if args.note:
        print(f"note: {args.note}")
    return 0


def cmd_release(args) -> int:
    try:
        leases.release(args.workstream, f"agent:{args.agent}", force=args.force)
    except leases.LeaseError as exc:
        print(f"release failed: {exc}", file=sys.stderr)
        return 1
    events.emit("lease.released",
                events.Actor(kind="agent", id=args.agent),
                events.Subject(kind="workstream", id=args.workstream),
                {"force": args.force})
    try:
        s = state.read()
        state.sync_leases(s)
        state.write(s)
    except state.StateError:
        pass
    print(f"released {args.workstream}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fsp.py",
                                     description="Session protocol driver (BUILD-SPEC §0)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("bootstrap", help="zero STATE.json + skeleton (fresh clone)")
    p.add_argument("--phase", default="P1-agentic-core")
    p.add_argument("--slice", default="VS-1")
    p.add_argument("--agent", default="owner")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_bootstrap)

    p = sub.add_parser("status", help="SYNC readout")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("claim", help="acquire a workstream lease (step 3)")
    p.add_argument("workstream")
    p.add_argument("--agent", required=True)
    p.add_argument("--session")
    p.add_argument("--ttl", type=int, default=90)
    p.set_defaults(func=cmd_claim)

    p = sub.add_parser("heartbeat", help="renew a lease (15m SLA)")
    p.add_argument("workstream")
    p.add_argument("--agent", required=True)
    p.set_defaults(func=cmd_heartbeat)

    p = sub.add_parser("slice", help="move the phase/slice pointer (ADR-008)")
    p.add_argument("slice", help="target slice, e.g. VS-4")
    p.add_argument("--agent", required=True)
    p.add_argument("--phase", help="also move the phase pointer")
    p.add_argument("--workstream", default=SLICE_WORKSTREAM,
                   help=f"lease that fences this write (default {SLICE_WORKSTREAM})")
    p.add_argument("--note", default="", help="why the slice moved")
    p.set_defaults(func=cmd_slice)

    p = sub.add_parser("release", help="release a lease")
    p.add_argument("workstream")
    p.add_argument("--agent", required=True)
    p.add_argument("--force", action="store_true", help="reaper/succession use only")
    p.set_defaults(func=cmd_release)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"fsp: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
