#!/usr/bin/env python3
"""pr.py — GitHub CLI wrapper for Marzneshin Agent OS.

Manages Pull Requests from the terminal with automatic invariant checks
(BUILD-SPEC §16.1, Invariants I3, I11, I15).

Usage:
    python3 scripts/pr.py create --task T-xxx --title "..." [--body "..."] [--draft]
    python3 scripts/pr.py status
    python3 scripts/pr.py checks [--watch]
    python3 scripts/pr.py diff
    python3 scripts/pr.py merge [--squash]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def format_pr_title(title: str | None, task: str | None) -> str:
    if not title:
        return ""
    if task:
        clean_task = task.strip()
        prefix = f"[{clean_task}]"
        if not title.startswith(prefix):
            return f"{prefix} {title}"
    return title


def build_gh_create_cmd(
    title: str | None = None,
    body: str | None = None,
    draft: bool = False,
    fill: bool = False,
) -> list[str]:
    cmd = ["gh", "pr", "create"]
    if fill:
        cmd.append("--fill")
    else:
        if title:
            cmd.extend(["--title", title])
        if body:
            cmd.extend(["--body", body])
    if draft:
        cmd.append("--draft")
    return cmd


def run_verify() -> bool:
    print("==> Running invariant verifier (scripts/verify.py)...")
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "verify.py")],
        cwd=REPO_ROOT,
    )
    return result.returncode == 0


def cmd_create(args: argparse.Namespace) -> int:
    if not args.skip_verify:
        if not run_verify():
            print("❌ Verification failed! Fix invariants before opening PR (or use --skip-verify).", file=sys.stderr)
            return 1
        print("✅ Pre-PR verification passed.")

    title = format_pr_title(args.title, args.task)
    gh_cmd = build_gh_create_cmd(
        title=title if not args.fill else None,
        body=args.body if not args.fill else None,
        draft=args.draft,
        fill=args.fill,
    )

    print(f"==> Executing: {' '.join(gh_cmd)}")
    res = subprocess.run(gh_cmd, cwd=REPO_ROOT)
    return res.returncode


def cmd_status(_args: argparse.Namespace) -> int:
    return subprocess.run(["gh", "pr", "status"], cwd=REPO_ROOT).returncode


def cmd_checks(args: argparse.Namespace) -> int:
    cmd = ["gh", "pr", "checks"]
    if args.watch:
        cmd.append("--watch")
    return subprocess.run(cmd, cwd=REPO_ROOT).returncode


def cmd_diff(_args: argparse.Namespace) -> int:
    return subprocess.run(["gh", "pr", "diff"], cwd=REPO_ROOT).returncode


def cmd_merge(args: argparse.Namespace) -> int:
    cmd = ["gh", "pr", "merge"]
    if args.squash:
        cmd.append("--squash")
    if args.delete_branch:
        cmd.append("--delete-branch")
    return subprocess.run(cmd, cwd=REPO_ROOT).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="GitHub PR helper for Marzneshin Agent OS")
    sub = parser.add_subparsers(dest="command", required=True)

    # create
    p_create = sub.add_parser("create", help="Create a Pull Request with pre-flight verification")
    p_create.add_argument("--task", help="Task ID (e.g. T-PR-CLI)")
    p_create.add_argument("--title", help="PR title")
    p_create.add_argument("--body", help="PR body description", default="")
    p_create.add_argument("--draft", action="store_true", help="Create as draft PR")
    p_create.add_argument("--fill", action="store_true", help="Auto-fill title and body from commit")
    p_create.add_argument("--skip-verify", action="store_true", help="Skip local verify.py check")
    p_create.set_defaults(func=cmd_create)

    # status
    p_status = sub.add_parser("status", help="Show PR status for current branch")
    p_status.set_defaults(func=cmd_status)

    # checks
    p_checks = sub.add_parser("checks", help="Show CI checks for current PR")
    p_checks.add_argument("--watch", action="store_true", help="Watch checks in real time")
    p_checks.set_defaults(func=cmd_checks)

    # diff
    p_diff = sub.add_parser("diff", help="Show diff for current PR")
    p_diff.set_defaults(func=cmd_diff)

    # merge
    p_merge = sub.add_parser("merge", help="Merge current PR")
    p_merge.add_argument("--squash", action="store_true", default=True, help="Use squash merge")
    p_merge.add_argument("--delete-branch", action="store_true", default=True, help="Delete head branch after merge")
    p_merge.set_defaults(func=cmd_merge)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
