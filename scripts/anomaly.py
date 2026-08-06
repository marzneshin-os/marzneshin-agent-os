#!/usr/bin/env python3
"""anomaly.py — manage the actor_seq anomaly registry (VS-4, ADR-006).

Raw events are immutable (§3.2). When a historical seq anomaly is understood,
fixed at the root, and documented in an ADR, register it here so the events
gate stops failing on explained history — while staying red for anything
unexplained. Registration is script-mediated and emits an audit event;
hand-editing state/events/_anomalies.json is forbidden like any state edit.

    anomaly.py list [--world prod]
    anomaly.py register --actor agent-qa-gate --day 2026-07-30 \
        --kind duplicate_seq --seqs 5,6 --event-ids id1,id2 \
        --adr decisions/ADR/ADR-006-....md --by momo [--note "..."]

Exit codes: 0 ok, 2 usage/validation error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import events  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="anomaly.py",
                                     description="actor_seq anomaly registry (ADR-006)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="list registered anomalies")
    p_list.add_argument("--world", default=None)
    p_list.add_argument("--json", action="store_true")

    p_reg = sub.add_parser("register", help="register an explained anomaly")
    p_reg.add_argument("--actor", required=True, help="actor partition, e.g. agent-qa-gate")
    p_reg.add_argument("--day", required=True, help="event day YYYY-MM-DD")
    p_reg.add_argument("--kind", required=True,
                       choices=["duplicate_seq", "missing_seq"])
    p_reg.add_argument("--seqs", required=True, help="comma list, e.g. 5,6")
    p_reg.add_argument("--event-ids", required=True,
                       help="comma list of the offending event_ids")
    p_reg.add_argument("--adr", required=True, help="decision record path (required)")
    p_reg.add_argument("--by", required=True, help="who registers (agent/human id)")
    p_reg.add_argument("--note", default="")

    args = parser.parse_args(argv)

    if args.cmd == "list":
        items = events.list_anomalies(world=args.world)
        if args.json:
            print(json.dumps(items, indent=2, ensure_ascii=False))
        else:
            if not items:
                print("no registered anomalies")
            for a in items:
                print(f"{a['actor']} {a['day']} {a['kind']} seqs={a['seqs']} "
                      f"adr={a['adr']} by={a['registered_by']}")
        return 0

    if args.cmd == "register":
        seqs = [int(s) for s in args.seqs.split(",") if s.strip()]
        ids = [s.strip() for s in args.event_ids.split(",") if s.strip()]
        if not seqs or not ids:
            print("anomaly: --seqs and --event-ids must be non-empty", file=sys.stderr)
            return 2
        entry = events.register_anomaly(
            actor_partition=args.actor, day=args.day, kind=args.kind,
            seqs=seqs, event_ids=ids, adr=args.adr, by=args.by, note=args.note)
        print(f"registered: {entry['actor']} {entry['day']} {entry['kind']} "
              f"seqs={entry['seqs']} adr={entry['adr']}")
        return 0

    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"anomaly: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
