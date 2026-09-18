#!/usr/bin/env python3
"""review.py — CLI for the Adversarial Reviewer (BUILD-SPEC §10.1, VS-5).

Usage:
    review.py check --author AGENT --lineage LINEAGE [--intent INTENT] [--paths P1,P2] [--emit]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import adversarial_reviewer  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="review.py", description="Adversarial Reviewer CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="review proposed changes")
    c.add_argument("--author", required=True, help="author agent ID")
    c.add_argument("--lineage", required=True, help="author agent lineage")
    c.add_argument("--intent", default="", help="intent of the change")
    c.add_argument("--paths", default="", help="comma-separated list of changed paths")
    c.add_argument("--diff-file", help="path to file containing diff")
    c.add_argument("--emit", action="store_true", help="emit review event to log")
    c.add_argument("--json", action="store_true", help="output json")

    args = parser.parse_args(argv)

    paths_list = [p.strip() for p in args.paths.split(",") if p.strip()]
    diff_text = ""
    if args.diff_file and Path(args.diff_file).exists():
        diff_text = Path(args.diff_file).read_text(encoding="utf-8")

    res = adversarial_reviewer.review_change(
        author=args.author,
        author_lineage=args.lineage,
        intent=args.intent,
        changes=paths_list,
        diff_text=diff_text,
        emit_event=args.emit,
    )

    if args.json:
        print(json.dumps(res, indent=2))
    else:
        mark = "REJECTED" if res["verdict"] == "REJECT" else "APPROVED"
        print(f"adversarial-review: {mark} by {res['reviewer']} ({res['reviewer_lineage']})")
        if res["reasons"]:
            print("reasons:")
            for r in res["reasons"]:
                print(f"  - {r}")

    return 1 if res["verdict"] == "REJECT" else 0


if __name__ == "__main__":
    raise SystemExit(main())
