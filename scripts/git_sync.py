#!/usr/bin/env python3
"""Safely verify and push a clean checkout to an explicit branch target."""
import argparse
import re
import subprocess
import sys
from pathlib import Path

if __package__:
    from .killswitch_state import RUNNING, read_verdict
else:
    from killswitch_state import RUNNING, read_verdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
_REMOTE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_PROTECTED_BRANCHES = {"main", "master", "develop", "production"}


class SyncError(RuntimeError):
    pass


def parse_push_target(target):
    if not isinstance(target, str) or target.count(":") != 1:
        raise ValueError("push target must use remote:branch form")
    remote, branch = target.split(":", 1)
    if not _REMOTE_PATTERN.fullmatch(remote) or not branch or branch.startswith("-"):
        raise ValueError("push target contains an invalid remote or branch")
    if branch in _PROTECTED_BRANCHES:
        raise ValueError(f"refusing to push to protected branch {branch!r}")
    return remote, branch


def run_cmd(command, cwd=PROJECT_ROOT, timeout=300):
    result = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        raise SyncError(f"command {command!r} failed: {detail}")
    return result


def require_running(root, phase):
    state_dir = Path(root) / "state"
    verdict = read_verdict(state_dir / "killswitch.json", state_dir / "STATE.json")
    if verdict != RUNNING:
        raise SyncError(f"kill switch is {verdict}; refusing sync {phase}")


def sync(push_target=None, root=PROJECT_ROOT):
    if not push_target:
        print("[ERROR] An explicit --push-target remote:branch is required.", file=sys.stderr)
        return 2
    try:
        remote, branch = parse_push_target(push_target)
        print("=" * 60)
        print("  MARZNESHIN OS — VERIFIED GIT SYNC")
        print("=" * 60)

        run_cmd(["git", "check-ref-format", "--branch", branch], cwd=root)
        require_running(root, "before fetch")
        print(f"[1/4] Fetching {remote}...")
        run_cmd(["git", "fetch", remote, "--quiet"], cwd=root)

        print("[2/4] Checking working tree...")
        status = run_cmd(
            ["git", "status", "--porcelain", "--untracked-files=all"], cwd=root
        ).stdout.strip()
        if status:
            raise SyncError("working tree is dirty; commit intended changes before syncing")

        print("[3/4] Running verification...")
        run_cmd([sys.executable, str(Path(root) / "scripts" / "verify.py")], cwd=root)

        print(f"[4/4] Pushing HEAD to {remote}:{branch}...")
        require_running(root, "before push")
        run_cmd(
            ["git", "push", remote, f"HEAD:refs/heads/{branch}"], cwd=root
        )
    except (SyncError, ValueError, OSError, subprocess.TimeoutExpired) as error:
        print(f"[ERROR] Git sync failed: {error}", file=sys.stderr)
        return 1

    print("[OK] Verification passed and the explicit push target accepted the update.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify and push to an explicit safe target")
    parser.add_argument(
        "--push-target",
        required=True,
        metavar="REMOTE:BRANCH",
        help="explicit remote and non-protected branch, for example origin:codex/task-name",
    )
    args = parser.parse_args(argv)
    return sync(args.push_target)


if __name__ == "__main__":
    sys.exit(main())
