#!/usr/bin/env python3
"""succession.py — CLI for the executable §11.1 succession protocol (VS-4).

Thin layer over scripts/lib/succession.py (shared logic lives in lib).

    succession.py run --agent config-engineer --workstream sim-config \
        --trigger member_removed [--reason WHY] [--dry-run]
    succession.py scan [--quiet] [--dry-run]
    succession.py triggers

Exit codes: 0 = flow completed (VERIFY green), 1 = flow failed or bad usage,
2 = the flow could not start at all (fail closed).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import clock, paths, succession  # noqa: E402
from lib.atomic import read_json  # noqa: E402


def cmd_run(args) -> int:
    try:
        report = succession.run(
            agent=args.agent, workstream=args.workstream, trigger=args.trigger,
            by=args.by, reason=args.reason, dry_run=args.dry_run)
    except succession.SuccessionError as exc:
        print(f"succession: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # the flow itself broke: fail closed
        print(f"succession: cannot run: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    for step in report.get("steps", []):
        mark = "ok" if step.get("ok") else "FAIL"
        detail = {k: v for k, v in step.items() if k not in ("step", "ok")}
        line = json.dumps(detail, ensure_ascii=False, default=str)
        print(f"[{mark}] {step['step']:<12} {line[:200]}")
    print(f"succession: {'GREEN' if report.get('ok') else 'RED'} | "
          f"{args.agent} -> {report.get('reassignment', {}).get('successor', '?')} "
          f"| trigger={args.trigger}" + (" | dry-run" if args.dry_run else ""))
    return 0 if report.get("ok") else 1


def cmd_scan(args) -> int:
    offboarding_file = paths.state_dir() / "OFFBOARDING.json"
    if not offboarding_file.exists():
        if not args.quiet:
            print("succession: no pending state/OFFBOARDING.json")
        return 0

    items = read_json(offboarding_file, default=[])
    if isinstance(items, dict):
        items = [items]
    elif not isinstance(items, list):
        items = []

    all_ok = True
    processed = 0
    for item in items:
        agent = item.get("agent")
        workstream = item.get("workstream")
        trigger = item.get("trigger", "offboarding_flag")
        reason = item.get("reason", "Automatic scan from state/OFFBOARDING.json")
        if not agent or not workstream:
            continue
        try:
            report = succession.run(
                agent=agent, workstream=workstream, trigger=trigger,
                by=args.by, reason=reason, dry_run=args.dry_run)
            if not report.get("ok"):
                all_ok = False
            else:
                processed += 1
        except Exception as exc:
            print(f"succession: scan failed for {agent}: {exc}", file=sys.stderr)
            all_ok = False

    if not args.dry_run and all_ok and processed > 0 and offboarding_file.exists():
        archive_dir = paths.state_dir() / "archive" / "offboarding"
        archive_dir.mkdir(parents=True, exist_ok=True)
        stamp = clock.now().strftime("%Y-%m-%dT%H%M%SZ")
        shutil.move(str(offboarding_file), str(archive_dir / f"offboarding-{stamp}.json"))
        print(f"succession: processed {processed} member(s), archived to {paths.rel(archive_dir)}")
    return 0 if all_ok else 1


def cmd_triggers(_args) -> int:
    for t in sorted(succession.TRIGGERS):
        print(t)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="succession.py",
                                description="Executable §11.1 succession protocol")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="execute the flow for one member")
    r.add_argument("--agent", required=True, help="member/agent being succeeded")
    r.add_argument("--workstream", required=True, help="workstream to FREEZE/REASSIGN")
    r.add_argument("--trigger", required=True,
                   help=f"one of: {', '.join(sorted(succession.TRIGGERS))}")
    r.add_argument("--reason", default="")
    r.add_argument("--by", default="succession")
    r.add_argument("--dry-run", action="store_true",
                   help="compute the whole flow, change nothing (not even the log)")
    r.add_argument("--json", action="store_true", help="print the full report JSON")

    s = sub.add_parser("scan", help="scan and process pending offboardings from state/OFFBOARDING.json")
    s.add_argument("--by", default="succession-scan")
    s.add_argument("--quiet", action="store_true")
    s.add_argument("--dry-run", action="store_true")

    t = sub.add_parser("triggers", help="list valid triggers")
    args = p.parse_args(argv)

    if args.cmd == "triggers":
        return cmd_triggers(args)
    if args.cmd == "scan":
        return cmd_scan(args)
    rc = cmd_run(args)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
