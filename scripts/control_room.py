#!/usr/bin/env python3
"""control_room.py — CLI for Control Room bidirectional sync engine (VS-6).

Usage:
    control_room.py sync [--json]
    control_room.py reverse --task TASK --field FIELD --value VALUE [--json]
    control_room.py status
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(1, str(REPO / "scripts"))

from lib import control_room_sync  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="control_room.py", description="Control Room Sync Engine CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sync", help="sync GitHub state to Control Room")
    s.add_argument("--json", action="store_true")

    r = sub.add_parser("reverse", help="reverse sync from Control Room to GitHub (exceptions only)")
    r.add_argument("--task", required=True, help="task ID")
    r.add_argument("--field", required=True, help="field name")
    r.add_argument("--value", required=True, help="field value")
    r.add_argument("--json", action="store_true")

    st = sub.add_parser("status", help="check control room adapter status")

    args = parser.parse_args(argv)

    if args.cmd == "sync":
        res = control_room_sync.sync_github_to_control_room()
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"control_room: synced {res['synced_count']} task(s) to Control Room across 5 workflows")
        return 0

    if args.cmd == "reverse":
        res = control_room_sync.sync_control_room_to_github(
            task_id=args.task,
            updated_fields={args.field: args.value}
        )
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            if res["applied"]:
                for a in res["applied"]:
                    print(f"control_room: APPLIED reverse sync for {a['field']} = {a['value']}")
            if res["rejected"]:
                for rj in res["rejected"]:
                    print(f"control_room: REJECTED reverse sync for {rj['field']}: {rj['reason']}", file=sys.stderr)
        return 0 if res["ok"] else 1

    if args.cmd == "status":
        ad = control_room_sync.get_default_adapter()
        h = ad.healthz()
        print(f"control_room_adapter: {'OK' if h.ok else 'ERROR'} | latency: {h.latency_ms}ms | detail: {h.detail}")
        return 0 if h.ok else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
