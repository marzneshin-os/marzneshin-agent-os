#!/usr/bin/env python3
"""Verification script for Marzneshin Autonomous OS.

Runs 7 functional checks to determine system health.
Exit code 0 = all checks pass, non-zero = at least one failure.

Checks:
    1. state/STATE.json exists and is valid JSON
    2. Kill switch verdict == "running"
    3. npm test passes
    4. npm run build passes
    5. No orphaned leases older than 1 hour
    6. state/HANDOFF.md exists and has required sections
    7. Master prompts immutability guard (>= 800 lines and required sections)
"""
import json
import subprocess
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

if __package__:
    from .killswitch_state import read_verdict
    from .sensitive_paths import is_sensitive_path
else:
    from killswitch_state import read_verdict
    from sensitive_paths import is_sensitive_path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

results = []

_NPM_COMMANDS = {
    "test": ("npm", "test"),
    "build": ("npm", "run", "build"),
}


def npm_command(script, windows=None):
    """Return a fixed npm invocation for the current platform."""
    if script not in _NPM_COMMANDS:
        raise ValueError(f"unsupported npm script: {script}")
    if windows is None:
        windows = os.name == "nt"
    argv = list(_NPM_COMMANDS[script])
    if windows:
        return ["cmd.exe", "/d", "/s", "/c", " ".join(argv)]
    return argv


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


def check_2_kill_switch(killswitch_file=None, state_file=None):
    state_dir = PROJECT_ROOT / "state"
    verdict = read_verdict(
        killswitch_file or state_dir / "killswitch.json",
        state_file or state_dir / "STATE.json",
    )
    return check("Kill switch == running", verdict == "running", f"verdict={verdict}")


def check_3_npm_test():
    try:
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        result = subprocess.run(
            npm_command("test"),
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
            shell=False,
            env=clean_env,
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
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        result = subprocess.run(
            npm_command("build"),
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
            shell=False,
            env=clean_env,
        )
        passed = result.returncode == 0
        detail = "Build succeeded" if passed else f"Exit code {result.returncode}"
        return check("npm run build passes", passed, detail)
    except subprocess.TimeoutExpired:
        return check("npm run build passes", False, "Timeout after 120s")
    except FileNotFoundError:
        return check("npm run build passes", False, "npm not found")


def check_5_orphaned_leases(leases_dir=None, now=None):
    leases_dir = Path(leases_dir) if leases_dir is not None else PROJECT_ROOT / "state" / "leases"
    symlinked_paths = [leases_dir]
    try:
        current = leases_dir.parent
        while current != PROJECT_ROOT and PROJECT_ROOT in current.parents:
            symlinked_paths.append(current)
            current = current.parent
    except OSError:
        return check("No orphaned leases", False, "Lease path could not be validated")
    if any(path.is_symlink() for path in symlinked_paths):
        return check("No orphaned leases", False, "Lease path contains a symlink (excluded)")
    if not leases_dir.exists():
        return check("No orphaned leases", True, "Leases directory not found (OK)")

    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        return check("No orphaned leases", False, "Reference time must include a timezone")
    malformed = []
    orphaned = []

    for lease_file in sorted(leases_dir.glob("*.json")):
        if is_sensitive_path(lease_file.name) or lease_file.is_symlink():
            malformed.append(f"{lease_file.name} (sensitive path excluded)")
            continue
        try:
            data = json.loads(lease_file.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("lease must be a JSON object")
            expires = data.get("expires_at")
            if not isinstance(expires, str) or not expires.strip():
                raise ValueError("lease expiry is missing")
            exp_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            if exp_dt.tzinfo is None or exp_dt.utcoffset() is None:
                raise ValueError("lease expiry is not timezone-aware")
            if exp_dt <= now:
                orphaned.append(lease_file.name)
        except (json.JSONDecodeError, ValueError, TypeError, OSError, OverflowError):
            malformed.append(f"{lease_file.name} (malformed)")

    if orphaned or malformed:
        details = []
        if orphaned:
            details.append(f"Orphaned: {orphaned}")
        if malformed:
            details.append(f"Malformed or excluded: {malformed}")
        return check("No orphaned leases", False, "; ".join(details))
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


def check_7_prompt_immutability():
    root_prompt = PROJECT_ROOT / "MASTER_PROMPT.md"
    agents_prompt = PROJECT_ROOT / ".agents" / "master_prompt.md"

    errors = []

    if not root_prompt.exists():
        errors.append("MASTER_PROMPT.md not found")
    else:
        content_root = root_prompt.read_text(encoding="utf-8")
        lines_root = content_root.splitlines()
        if len(lines_root) < 800:
            errors.append(f"MASTER_PROMPT.md has {len(lines_root)} lines (expected >= 800)")
        required_sections = ["§0", "§1", "§2", "§4", "§8", "§9", "§12"]
        missing_root = [s for s in required_sections if s not in content_root]
        if missing_root:
            errors.append(f"MASTER_PROMPT.md missing sections: {missing_root}")

    if not agents_prompt.exists():
        errors.append(".agents/master_prompt.md not found")
    else:
        content_agents = agents_prompt.read_text(encoding="utf-8")
        lines_agents = content_agents.splitlines()
        if len(lines_agents) < 800:
            errors.append(f".agents/master_prompt.md has {len(lines_agents)} lines (expected >= 800)")
        if "# 🧠 Master Prompt V3" not in content_agents:
            errors.append(".agents/master_prompt.md missing '# 🧠 Master Prompt V3' header")

    if errors:
        return check("Master prompts immutability guard", False, "; ".join(errors))

    return check(
        "Master prompts immutability guard",
        True,
        f"MASTER_PROMPT.md ({len(lines_root)} lines), .agents/master_prompt.md ({len(lines_agents)} lines)",
    )


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
    check_7_prompt_immutability()

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
