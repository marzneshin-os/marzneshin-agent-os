#!/usr/bin/env python3
"""Automated Two-Key Verification Gate for Marzneshin Autonomous OS.

Runs both verification keys and produces a combined verdict.
Key 1 (QA Gate): scripts/verify.py — all 6 checks green
Key 2 (Adversarial): git diff audit — no metric gaming, no mock shortcuts

Commands:
    run                - Execute full Two-Key verification
    key1               - Run only Key 1 (QA Gate)
    key2 [base_ref]    - Run only Key 2 (Adversarial audit)
"""
import json
import subprocess
import sys
import re
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
RESULTS_DIR = PROJECT_ROOT / "state" / "events"


def run_key1():
    """Key 1: QA Gate — scripts/verify.py must pass all checks."""
    print("🔑 KEY 1: QA Gate — Running scripts/verify.py")
    print("-" * 50)

    try:
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "verify.py")],
            capture_output=True, text=True, timeout=600, cwd=str(PROJECT_ROOT),
        )
        passed = result.returncode == 0
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        return {"key": "key1_qa_gate", "passed": passed, "exit_code": result.returncode}
    except subprocess.TimeoutExpired:
        print("❌ Timeout after 600s")
        return {"key": "key1_qa_gate", "passed": False, "exit_code": -1}
    except Exception as e:
        print(f"❌ Error: {e}")
        return {"key": "key1_qa_gate", "passed": False, "exit_code": -1}


def run_key2(base_ref=None):
    """Key 2: Adversarial Review — audit git diff for violations."""
    if base_ref is None:
        # Check uncommitted changes first; if clean, audit against HEAD~1
        try:
            head_check = subprocess.run(
                ["git", "diff", "--stat", "HEAD"],
                capture_output=True, text=True, timeout=30,
                cwd=str(PROJECT_ROOT), shell=True,
            )
            base_ref = "HEAD" if head_check.stdout.strip() else "HEAD~1"
        except Exception:
            base_ref = "HEAD"

    print(f"\n🔑 KEY 2: Adversarial Review — Auditing diff against {base_ref}")
    print("-" * 50)

    violations = []

    try:
        result = subprocess.run(
            ["git", "diff", "--stat", base_ref],
            capture_output=True, text=True, timeout=30,
            cwd=str(PROJECT_ROOT), shell=True,
        )
        diff_stat = result.stdout.strip()

        if not diff_stat:
            print("  No changes detected (clean working tree)")
            return {"key": "key2_adversarial", "passed": True, "violations": [], "note": "clean tree"}
    except Exception:
        diff_stat = ""

    try:
        result = subprocess.run(
            ["git", "diff", base_ref],
            capture_output=True, text=True, timeout=30,
            cwd=str(PROJECT_ROOT), shell=True,
        )
        diff_content = result.stdout
    except Exception:
        diff_content = ""

    current_file = ""
    added_src_lines = []
    added_all_lines = []

    for line in diff_content.splitlines():
        if line.startswith("diff --git"):
            parts = line.split()
            current_file = parts[-1].lstrip("b/") if len(parts) >= 4 else ""
        elif line.startswith("+") and not line.startswith("+++"):
            added_text = line[1:]
            added_all_lines.append((current_file, added_text))
            if not current_file.startswith("test/"):
                added_src_lines.append((current_file, added_text))

    # Check for test skipping anywhere in diff
    for file, line in added_all_lines:
        if re.search(r"\b(it|test|describe)\.skip\(", line):
            violations.append(f"Test skipping detected in {file}: {line.strip()}")
        if re.search(r"\b(it|test|describe)\.only\(", line):
            violations.append(f"test.only() detected in {file}: {line.strip()}")

    # Check for metric gaming and forced exits in production/source files
    for file, line in added_src_lines:
        if re.search(r"mock.*return.*true", line, re.IGNORECASE):
            violations.append(f"Mock returning hardcoded true in {file}: {line.strip()}")
        if re.search(r"console\.log.*pass", line, re.IGNORECASE):
            violations.append(f"Console.log('pass') in {file}: {line.strip()}")
        if re.search(r"catch\s*\([^)]*\)\s*\{\s*\}", line):
            violations.append(f"Empty catch block in {file}: {line.strip()}")

    # Check for hardcoded secrets anywhere in added lines
    for file, line in added_all_lines:
        if re.search(r"(?:BEGIN (?:RSA |DSA )?PRIVATE KEY)", line):
            violations.append(f"🔴 SECURITY: Private key in {file}")
        elif re.search(r"(?:password|secret|api_key|token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]", line, re.IGNORECASE):
            # Exclude known mock/dummy tokens in tests
            if not file.startswith("test/"):
                violations.append(f"🔴 SECURITY: Possible hardcoded secret in {file}")

    passed = len(violations) == 0

    if violations:
        print("  Violations found:")
        for v in violations:
            print(f"  ❌ {v}")
    else:
        print("  ✅ No metric gaming or security violations detected")

    return {"key": "key2_adversarial", "passed": passed, "violations": violations}


def run_full():
    """Execute full Two-Key verification."""
    print("=" * 60)
    print("  TWO-KEY VERIFICATION GATE")
    print("=" * 60)

    k1 = run_key1()
    k2 = run_key2()

    both_pass = k1["passed"] and k2["passed"]

    print("\n" + "=" * 60)
    k1_icon = "✅" if k1["passed"] else "❌"
    k2_icon = "✅" if k2["passed"] else "❌"
    print(f"  Key 1 (QA Gate):        {k1_icon} {'APPROVED' if k1['passed'] else 'REJECTED'}")
    print(f"  Key 2 (Adversarial):    {k2_icon} {'APPROVED' if k2['passed'] else 'REJECTED'}")
    print("-" * 60)

    if both_pass:
        print("  VERDICT: ✅ APPROVED — Both keys confirm. Safe to emit receipt.")
    else:
        print("  VERDICT: ❌ REJECTED — Fix failures before proceeding.")
    print("=" * 60)

    now = datetime.now(timezone.utc)
    record = {
        "event_id": f"twokey-{now.strftime('%Y%m%d%H%M%S')}",
        "timestamp": now.isoformat(),
        "agent": "two-key-gate",
        "type": "verification_passed" if both_pass else "verification_failed",
        "description": f"Two-Key verification {'passed' if both_pass else 'failed'}",
        "metadata": {"key1": k1, "key2": k2},
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    event_file = RESULTS_DIR / f"{now.strftime('%Y%m%d-%H%M%S')}-two-key-{'pass' if both_pass else 'fail'}.json"
    with open(event_file, "w") as f:
        json.dump(record, f, indent=2)

    return 0 if both_pass else 1


COMMANDS = {
    "run": run_full,
    "key1": lambda: print(json.dumps(run_key1(), indent=2)) or 0,
    "key2": lambda: print(json.dumps(run_key2(sys.argv[2] if len(sys.argv) > 2 else "HEAD~1"), indent=2)) or 0,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"Usage: {sys.argv[0]} {{run|key1|key2}} [base_ref]")
        return 1
    return COMMANDS[sys.argv[1]]()


if __name__ == "__main__":
    sys.exit(main())
