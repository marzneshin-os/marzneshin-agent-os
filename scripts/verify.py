#!/usr/bin/env python3
"""Verification script for Marzneshin Autonomous OS.

Runs 6 functional checks to determine system health.
Exit code 0 = all checks pass, non-zero = at least one failure.

Checks:
    1. state/STATE.json exists and is valid JSON
    2. Kill switch verdict == "running"
    3. npm test passes
    4. npm run build passes
    5. No orphaned leases older than 1 hour
    6. state/HANDOFF.md exists and has required sections
"""
import json
import subprocess
import sys
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

results = []


def check(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results.append({"name": name, "passed": passed, "detail": detail})
    icon = "✅" if passed else "❌"
    print(f"  [{status}] {icon} {name}" + (f" — {detail}" if detail else ""))
    return passed


def check_1_state_json():
    state_file = PROJECT_ROOT / "state" / "STATE.json"
    if not state_file.exists():
        return check("STATE.json exists and valid", False, "File not found")
    try:
        with open(state_file, "r") as f:
            data = json.load(f)
        required_keys = ["version", "phase", "kill_switch", "agents", "receipt_chain"]
        missing = [k for k in required_keys if k not in data]
        if missing:
            return check("STATE.json exists and valid", False, f"Missing keys: {missing}")
        return check("STATE.json exists and valid", True, f"v{data.get('version', '?')}, phase={data.get('phase', '?')}")
    except json.JSONDecodeError as e:
        return check("STATE.json exists and valid", False, f"Invalid JSON: {e}")


def check_2_kill_switch():
    state_file = PROJECT_ROOT / "state" / "STATE.json"
    ks_file = PROJECT_ROOT / "state" / "killswitch.json"

    verdict = None
    if ks_file.exists():
        try:
            with open(ks_file, "r") as f:
                verdict = json.load(f).get("verdict")
        except (json.JSONDecodeError, KeyError):
            pass

    if verdict is None and state_file.exists():
        try:
            with open(state_file, "r") as f:
                verdict = json.load(f).get("kill_switch", {}).get("verdict")
        except (json.JSONDecodeError, KeyError):
            pass

    if verdict is None:
        return check("Kill switch == running", False, "No kill switch state found (fail-closed)")

    return check("Kill switch == running", verdict == "running", f"verdict={verdict}")


def check_3_npm_test():
    try:
        result = subprocess.run(
            "npm test",
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
            shell=True,
        )
        passed = result.returncode == 0
        detail = "All tests passed" if passed else f"Exit code {result.returncode}"
        if not passed and result.stderr:
            last_lines = result.stderr.strip().split("\n")[-3:]
            detail += " | " + " ".join(last_lines)
        return check("npm test passes", passed, detail)
    except subprocess.TimeoutExpired:
        return check("npm test passes", False, "Timeout after 300s")
    except FileNotFoundError:
        return check("npm test passes", False, "npm not found")


def check_4_npm_build():
    try:
        result = subprocess.run(
            "npm run build",
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
            shell=True,
        )
        passed = result.returncode == 0
        detail = "Build succeeded" if passed else f"Exit code {result.returncode}"
        return check("npm run build passes", passed, detail)
    except subprocess.TimeoutExpired:
        return check("npm run build passes", False, "Timeout after 120s")
    except FileNotFoundError:
        return check("npm run build passes", False, "npm not found")


def check_5_orphaned_leases():
    leases_dir = PROJECT_ROOT / "state" / "leases"
    if not leases_dir.exists():
        return check("No orphaned leases", True, "Leases directory not found (OK)")

    now = datetime.now(timezone.utc)
    max_age = timedelta(hours=1)
    orphaned = []

    for lease_file in leases_dir.glob("*.json"):
        try:
            with open(lease_file, "r") as f:
                data = json.load(f)
            expires = data.get("expires_at")
            if expires:
                exp_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                if exp_dt < now:
                    orphaned.append(lease_file.name)
        except (json.JSONDecodeError, ValueError, KeyError):
            orphaned.append(f"{lease_file.name} (corrupt)")

    if orphaned:
        return check("No orphaned leases", False, f"Orphaned: {orphaned}")
    return check("No orphaned leases", True, "No expired leases found")


def check_6_handoff():
    handoff_file = PROJECT_ROOT / "state" / "HANDOFF.md"
    if not handoff_file.exists():
        return check("HANDOFF.md exists with required sections", False, "File not found")

    content = handoff_file.read_text()
    required_sections = ["Current State", "What Was Done", "What Needs To Happen Next"]
    missing = [s for s in required_sections if s not in content]

    if missing:
        return check("HANDOFF.md exists with required sections", False, f"Missing sections: {missing}")
    return check("HANDOFF.md exists with required sections", True, f"{len(content)} bytes")


def main():
    print("=" * 60)
    print("  MARZNESHIN AUTONOMOUS OS — VERIFICATION REPORT")
    print("=" * 60)
    print()

    check_1_state_json()
    check_2_kill_switch()
    check_3_npm_test()
    check_4_npm_build()
    check_5_orphaned_leases()
    check_6_handoff()

    print()
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print("-" * 60)
    print(f"  RESULT: {passed}/{total} checks passed")

    if passed == total:
        print("  STATUS: ✅ ALL CHECKS GREEN — System verified")
    else:
        failed = [r["name"] for r in results if not r["passed"]]
        print(f"  STATUS: ❌ FAILURES DETECTED — {failed}")

    print("-" * 60)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
