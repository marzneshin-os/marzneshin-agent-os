#!/usr/bin/env python3
"""handoff.py — CLI for Handoff Guardian and continuity scoring (VS-5).

Usage:
    handoff.py verify [--path PATH]
    handoff.py score [--json] [--emit]
    handoff.py reap [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import handoff_guardian, paths  # noqa: E402
import reaper  # noqa: E402


def cmd_verify(args) -> int:
    path = Path(args.path) if args.path else None
    res = handoff_guardian.verify_handoff(path)
    if res["ok"]:
        print(f"handoff: OK | Updated: {res['updated']} | By: {res['by']} | Slice: {res['slice']}")
        return 0
    print("handoff: FAILED", file=sys.stderr)
    for r in res["reasons"]:
        print(f"  - {r}", file=sys.stderr)
    return 1


def cmd_score(args) -> int:
    res = handoff_guardian.compute_continuity_score(emit_event=args.emit)
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"continuity_score: {res['score']} ({res['verdict']})")
        for k, v in res["factors"].items():
            print(f"  {k:<20}: {v:.2f}")
    return 0 if res["verdict"] == "PASS" else 1


def cmd_reap(args) -> int:
    actions = reaper.reap(dry_run=args.dry_run, reaper_id="handoff-guardian")
    if not actions:
        print("handoff: no zombie leases found")
        return 0
    print(f"handoff: reaped {len(actions)} zombie lease(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="handoff.py", description="Handoff Guardian CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("verify", help="verify state/HANDOFF.md format and presence")
    v.add_argument("--path", help="path to custom HANDOFF.md")

    s = sub.add_parser("score", help="compute operational continuity score")
    s.add_argument("--json", action="store_true", help="output JSON")
    s.add_argument("--emit", action="store_true", help="emit continuity.scored event")

    r = sub.add_parser("reap", help="reap zombie leases")
    r.add_argument("--dry-run", action="store_true")

    args = parser.parse_args(argv)
    if args.cmd == "verify":
        return cmd_verify(args)
    if args.cmd == "score":
        return cmd_score(args)
    if args.cmd == "reap":
        return cmd_reap(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
