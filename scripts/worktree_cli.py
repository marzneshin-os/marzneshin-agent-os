#!/usr/bin/env python3
"""Worktree CLI — Multi-Agent Parallel Execution via Git Worktrees (Boris Cherny Architecture)."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKTREES_DIR = REPO_ROOT / ".worktrees"


def run_git(args: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    res = subprocess.run(
        ["git"] + args,
        cwd=str(cwd or REPO_ROOT),
        capture_output=True,
        text=True,
    )
    return res.returncode, res.stdout.strip(), res.stderr.strip()


def cmd_create(branch: str, base: str = "main") -> int:
    WORKTREES_DIR.mkdir(exist_ok=True)
    target = WORKTREES_DIR / branch
    if target.exists():
        print(f"[!] Worktree path already exists: {target}")
        return 1

    print(f"[*] Creating worktree for branch '{branch}' at {target}...")
    code, stdout, stderr = run_git(["worktree", "add", "-b", branch, str(target), base])
    if code != 0:
        # Maybe branch already exists? Try without -b
        code2, stdout2, stderr2 = run_git(["worktree", "add", str(target), branch])
        if code2 != 0:
            print(f"[x] Error creating worktree: {stderr or stderr2}")
            return 1

    # Link or copy essential files if present
    for fname in [".env", ".env.local"]:
        src = REPO_ROOT / fname
        dst = target / fname
        if src.exists() and not dst.exists():
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass

    print(f"[+] Worktree created successfully at: {target}")
    print(f"[*] To launch an isolated subagent or terminal session:")
    print(f"    cd {target}")
    return 0


def cmd_list(as_json: bool = False) -> int:
    code, stdout, stderr = run_git(["worktree", "list", "--porcelain"])
    if code != 0:
        print(f"[x] Git worktree list failed: {stderr}")
        return 1

    worktrees = []
    current: dict[str, str] = {}
    for line in stdout.splitlines():
        if not line.strip():
            if current:
                worktrees.append(current)
                current = {}
            continue
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            current[parts[0]] = parts[1]
        elif len(parts) == 1:
            current[parts[0]] = "true"
    if current:
        worktrees.append(current)

    if as_json:
        print(json.dumps(worktrees, indent=2))
        return 0

    print("=" * 70)
    print("  Active Git Worktrees (Boris Cherny Parallelism Architecture)")
    print("=" * 70)
    for wt in worktrees:
        path = wt.get("worktree", "")
        branch = wt.get("branch", "detached")
        head = wt.get("HEAD", "")[:8]
        is_bare = "bare" in wt
        status = (
            "BARE" if is_bare else ("MAIN" if path == str(REPO_ROOT) else "WORKTREE")
        )
        print(f"[{status}] {branch} ({head}) -> {path}")
    print("=" * 70)
    return 0


def cmd_remove(branch: str, force: bool = False) -> int:
    target = WORKTREES_DIR / branch
    if not target.exists():
        print(f"[!] Worktree path does not exist: {target}")
        return 1

    print(f"[*] Removing worktree '{branch}' at {target}...")
    args = ["worktree", "remove", str(target)]
    if force:
        args.append("--force")
    code, stdout, stderr = run_git(args)
    if code != 0:
        print(f"[x] Failed to remove worktree: {stderr}")
        return 1

    print(f"[+] Worktree '{branch}' removed successfully.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Git Worktree Manager for Multi-Agent Parallelism"
    )
    sub = parser.add_subparsers(dest="action", required=True)

    create_p = sub.add_parser("create", help="Create new worktree for branch")
    create_p.add_argument("branch", help="Branch name")
    create_p.add_argument("--base", default="main", help="Base branch (default: main)")

    list_p = sub.add_parser("list", help="List active worktrees")
    list_p.add_argument("--json", action="store_true", help="Output JSON")

    remove_p = sub.add_parser("remove", help="Remove existing worktree")
    remove_p.add_argument("branch", help="Branch name")
    remove_p.add_argument("--force", "-f", action="store_true", help="Force removal")

    args = parser.parse_args()
    if args.action == "create":
        return cmd_create(args.branch, args.base)
    elif args.action == "list":
        return cmd_list(args.json)
    elif args.action == "remove":
        return cmd_remove(args.branch, args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
