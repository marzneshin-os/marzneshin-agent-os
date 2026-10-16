#!/usr/bin/env python3
"""
Marzneshin Autonomous OS — Always-Alive Autonomous Daemon
Continuously monitors local filesystem changes, executes Two-Key verification,
and autonomously synchronizes with origin remote upon green verification.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WATCH_DIRS = [
    PROJECT_ROOT / "src",
    PROJECT_ROOT / "test",
    PROJECT_ROOT / "plugin",
    PROJECT_ROOT / "scripts",
]
WATCH_FILES = [
    PROJECT_ROOT / "package.json",
    PROJECT_ROOT / "tsconfig.json",
    PROJECT_ROOT / "tsdown.config.ts",
]
IGNORE_SUBSTRINGS = [
    "node_modules",
    "dist",
    "data",
    ".git",
    ".gemini",
    "coverage",
    "DAEMON_STATUS.json",
    "daemon.log",
]

STATE_DIR = PROJECT_ROOT / "state"
STATUS_FILE = STATE_DIR / "DAEMON_STATUS.json"
LOG_FILE = STATE_DIR / "daemon.log"


def log(msg: str):
    ts = datetime.now(timezone.utc).isoformat()
    line = f"[{ts}] {msg}"
    print(line)
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def write_daemon_status(status_data: dict):
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(status_data, f, indent=2)
    except Exception as e:
        log(f"Failed to write daemon status: {e}")


def get_file_snapshot() -> dict:
    snapshot = {}
    for wd in WATCH_DIRS:
        if not wd.exists():
            continue
        for root, dirs, files in os.walk(wd):
            if any(ign in root for ign in IGNORE_SUBSTRINGS):
                continue
            for file in files:
                fpath = Path(root) / file
                if any(ign in str(fpath) for ign in IGNORE_SUBSTRINGS):
                    continue
                try:
                    snapshot[str(fpath)] = fpath.stat().st_mtime
                except OSError:
                    pass
    for wf in WATCH_FILES:
        if wf.exists():
            try:
                snapshot[str(wf)] = wf.stat().st_mtime
            except OSError:
                pass
    return snapshot


def is_killswitch_active() -> bool:
    try:
        state_file = STATE_DIR / "STATE.json"
        if state_file.exists():
            data = json.loads(state_file.read_text(encoding="utf-8"))
            if data.get("kill_switch") in ["paused", "stopped"]:
                return True
    except Exception:
        pass
    return False


def run_verification() -> bool:
    log("▶ Triggering Two-Key verification suite (scripts/verify.py)...")
    try:
        proc = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "verify.py")],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        passed = proc.returncode == 0
        if passed:
            log("✅ Verification SUCCESSFUL: All 6/6 checks passed.")
        else:
            log(f"❌ Verification FAILED with code {proc.returncode}:\n{proc.stdout}")
        return passed
    except Exception as e:
        log(f"❌ Verification error: {e}")
        return False


def run_git_sync():
    log("▶ Triggering Autonomous Git Sync (scripts/git_sync.py)...")
    try:
        proc = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "git_sync.py")],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode == 0:
            log("✅ Git Sync SUCCESSFUL:\n" + proc.stdout.strip())
        else:
            log(f"⚠️ Git Sync returned code {proc.returncode}:\n{proc.stderr}")
    except Exception as e:
        log(f"❌ Git Sync error: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Marzneshin Autonomous Always-Alive Daemon"
    )
    parser.add_argument(
        "--auto-sync",
        action="store_true",
        help="Automatically sync and push to origin when tests pass",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=3,
        help="Seconds between filesystem scans (default: 3)",
    )
    parser.add_argument(
        "--debounce",
        type=int,
        default=4,
        help="Seconds of quiet time after file changes before running verification (default: 4)",
    )
    args = parser.parse_args()

    log("============================================================")
    log("  MARZNESHIN OS — AUTONOMOUS ALWAYS-ALIVE DAEMON STARTED")
    log("============================================================")
    log(f"Watching: {[str(d.name) for d in WATCH_DIRS]}")
    log(f"Auto-Sync to Remote: {'ENABLED' if args.auto_sync else 'DISABLED (verification-only)'}")

    last_snapshot = get_file_snapshot()
    pending_change_time = None
    last_verified_time = None
    last_sync_time = None
    iteration = 0

    status = {
        "daemon_status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "last_health_check": datetime.now(timezone.utc).isoformat(),
        "auto_sync_enabled": args.auto_sync,
        "last_verification_passed": None,
        "tracked_files": len(last_snapshot),
    }
    write_daemon_status(status)

    try:
        while True:
            time.sleep(args.poll_interval)
            iteration += 1

            # Check kill switch
            if is_killswitch_active():
                log("⚠️ Kill switch activated. Daemon paused.")
                status["daemon_status"] = "paused_by_killswitch"
                write_daemon_status(status)
                time.sleep(10)
                continue

            current_snapshot = get_file_snapshot()

            # Detect differences
            has_changes = False
            for fpath, mtime in current_snapshot.items():
                if fpath not in last_snapshot or last_snapshot[fpath] != mtime:
                    has_changes = True
                    break
            if not has_changes and len(current_snapshot) != len(last_snapshot):
                has_changes = True

            now = time.time()

            if has_changes:
                log("⚡ Filesystem changes detected. Waiting for debounce quiet period...")
                last_snapshot = current_snapshot
                pending_change_time = now

            # If quiet period has elapsed after changes, trigger verification
            if pending_change_time and (now - pending_change_time >= args.debounce):
                pending_change_time = None
                log("🔄 Quiet period reached. Executing automated verification cycle...")
                passed = run_verification()
                last_verified_time = now
                status["last_verification_passed"] = passed
                status["last_verified_at"] = datetime.now(timezone.utc).isoformat()
                write_daemon_status(status)

                if passed and args.auto_sync:
                    run_git_sync()
                    last_sync_time = now
                    status["last_synced_at"] = datetime.now(timezone.utc).isoformat()
                    write_daemon_status(status)

            # Periodic heartbeat (every 60s)
            if iteration % 20 == 0:
                status["last_health_check"] = datetime.now(timezone.utc).isoformat()
                status["daemon_status"] = "active"
                status["tracked_files"] = len(current_snapshot)
                write_daemon_status(status)

    except KeyboardInterrupt:
        log("🛑 Daemon received shutdown signal (SIGINT). Exiting cleanly.")
        status["daemon_status"] = "stopped"
        write_daemon_status(status)
        sys.exit(0)


if __name__ == "__main__":
    main()
