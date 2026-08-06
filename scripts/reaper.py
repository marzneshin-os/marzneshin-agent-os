#!/usr/bin/env python3
"""reaper.py — tombstones for tasks that died without a receipt (G5, §3.3).

The invariant "every task has exactly one receipt" only survives contact with
reality if a crash also produces a receipt. The reaper is who writes it:

  1. find zombie leases (expired TTL or heartbeat SLA missed)
  2. for each, revoke the lease with a fresh fencing token — succession STEP 1
     (§11.1): the dead holder's in-flight writes must be rejected even if its
     process wakes up
  3. write a `crashed` tombstone receipt for every open task on that
     workstream, so receipt coverage stays 100% without lying about outcomes
  4. emit lease.revoked + task.crashed events

Run by the `heartbeat` workflow every 15 minutes. Safe to run by hand:
idempotent — a task that already has a receipt is left alone.

    reaper.py            reap all zombies
    reaper.py --dry-run  report what would be reaped, change nothing
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import clock, events, leases, paths, receipts, state  # noqa: E402


def reap(*, dry_run: bool = False, reaper_id: str = "reaper") -> list[dict]:
    actor = events.Actor(kind="system", id=reaper_id)
    actions: list[dict] = []

    try:
        s = state.read()
    except state.StateError:
        s = None

    for zombie in leases.find_zombies():
        ws = zombie["workstream"]
        holder = zombie["holder"]
        open_tasks: list[str] = []
        if s:
            open_tasks = list(s.get("workstreams", {}).get(ws, {}).get("open_tasks", []))
        # If STATE is silent, the dead holder's open tasks are unknown. The
        # tombstone still has to exist (G5), so we synthesize one for the
        # workstream itself rather than skipping.
        if not open_tasks:
            open_tasks = [f"T-UNKNOWN-{ws}-{zombie['fencing_token']}"]

        record = {"workstream": ws, "holder": holder,
                  "reasons": zombie["reasons"], "tasks": [], "dry_run": dry_run}

        for task_id in open_tasks:
            existing = receipts.read(task_id)
            if existing and existing.get("status"):
                record["tasks"].append({"task_id": task_id, "action": "skipped",
                                        "reason": f"receipt already exists "
                                                  f"({existing.get('status')})"})
                continue
            record["tasks"].append({"task_id": task_id, "action": "tombstone"})
            if not dry_run:
                path = receipts.write_tombstone(
                    task_id=task_id, agent=holder.replace("agent:", ""),
                    workstream=ws,
                    reason="; ".join(zombie["reasons"]),
                    fencing_token=zombie["fencing_token"],
                    evidence=f"state/locks/{paths.slug(ws)}.lock.json")
                events.emit("task.crashed", actor,
                            events.Subject(kind="task", id=task_id),
                            {"workstream": ws, "holder": holder,
                             "reasons": zombie["reasons"],
                             "receipt": paths.rel(path)})

        if not dry_run:
            token = leases.revoke(ws, revoked_by=reaper_id,
                                  reason="reaper: " + "; ".join(zombie["reasons"]))
            record["burned_fencing_token"] = token
            events.emit("lease.revoked", actor,
                        events.Subject(kind="workstream", id=ws),
                        {"holder": holder, "burned_fencing_token": token,
                         "reasons": zombie["reasons"]})
            if s:
                state.upsert_workstream(s, ws, health="red")
        actions.append(record)

    if actions and not dry_run and s:
        state.sync_leases(s)
        state.write(s)
    return actions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reaper.py",
                                     description="Tombstone crashed tasks (G5)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    actions = reap(dry_run=args.dry_run)
    if args.json:
        print(json.dumps({"reaped": len(actions), "actions": actions},
                         indent=2, ensure_ascii=False))
    elif not actions:
        print("no zombie leases — nothing to reap")
    else:
        for a in actions:
            print(f"reaped {a['workstream']} (holder {a['holder']}, "
                  f"{', '.join(a['reasons'])})")
            for t in a["tasks"]:
                print(f"    {t['action']}: {t['task_id']}"
                      + (f" — {t.get('reason')}" if t.get("reason") else ""))
            if "burned_fencing_token" in a:
                print(f"    fencing token burned: {a['burned_fencing_token']}")
        if args.dry_run:
            print("\n(dry run — nothing was changed)")
    # Exit 1 when work was found: the heartbeat workflow treats "reaper had to
    # act" as a signal worth notifying, not as a failure of the reaper itself.
    return 1 if actions else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"reaper: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
