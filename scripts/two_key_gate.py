#!/usr/bin/env python3
"""Automated Two-Key Verification Gate for Marzneshin Autonomous OS."""
import json
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

if __package__:
    from .sensitive_paths import is_sensitive_path
else:
    from sensitive_paths import is_sensitive_path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
RESULTS_DIR = PROJECT_ROOT / "state" / "events"
def run_key1():
    print("🔑 KEY 1: QA Gate — Running scripts/verify.py")
    print("-" * 50)
    try:
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "verify.py")],
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(PROJECT_ROOT),
            shell=False,
        )
        passed = result.returncode == 0
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        return {"key": "key1_qa_gate", "passed": passed, "exit_code": result.returncode}
    except subprocess.TimeoutExpired:
        print("❌ Timeout after 600s")
        return {"key": "key1_qa_gate", "passed": False, "exit_code": -1}
    except (OSError, subprocess.SubprocessError) as error:
        print(f"❌ Error: {error}")
        return {"key": "key1_qa_gate", "passed": False, "exit_code": -1}


def _git(args, root=PROJECT_ROOT):
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(root),
        shell=False,
    )


def _git_failure(result, command):
    detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
    return f"Git {command} failed: {detail}"


def _parse_status_paths(output):
    records = output.split("\0")
    entries = []
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if len(record) < 4 or record[2] != " ":
            raise ValueError("Git status returned malformed porcelain output")
        status = record[:2]
        path = record[3:]
        if not path:
            raise ValueError("Git status returned an empty path")
        entries.append((status, path))
        if "R" in status or "C" in status:
            if index >= len(records) or not records[index]:
                raise ValueError("Git status omitted a rename or copy path")
            entries.append((status, records[index]))
            index += 1
    return entries


def _diff_added_lines(diff_content):
    current_file = ""
    added = []
    for line in diff_content.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
        elif line.startswith("diff --git "):
            current_file = ""
        elif line.startswith("+") and not line.startswith("+++"):
            added.append((current_file, line[1:]))
    return added


def _read_untracked_lines(root, names):
    root = Path(root).resolve()
    added = []
    for name in names:
        if not name:
            continue
        if is_sensitive_path(name):
            raise OSError(f"sensitive untracked path excluded: {name}")
        try:
            relative_candidate = (root / name).relative_to(root)
        except ValueError as error:
            raise OSError(f"untracked path escapes repository root: {name}") from error
        candidate = root
        for part in relative_candidate.parts:
            if part == "..":
                raise OSError(f"untracked path escapes repository root: {name}")
            candidate = candidate / part
            if candidate.is_symlink():
                raise OSError(f"untracked symlink path excluded: {name}")
        path = candidate.resolve()
        try:
            relative_target = path.relative_to(root)
        except ValueError as error:
            raise OSError(f"untracked path escapes repository root: {name}") from error
        if is_sensitive_path(relative_target.as_posix()):
            raise OSError(f"sensitive untracked path excluded: {name}")
        content = path.read_text(encoding="utf-8", errors="replace")
        added.extend((name.replace("\\", "/"), line) for line in content.splitlines())
    return added


def run_key2(base_ref=None):
    """Audit tracked, staged, and untracked changes; Git errors fail closed."""
    if base_ref is not None and (not isinstance(base_ref, str) or not base_ref.strip()):
        return {
            "key": "key2_adversarial",
            "passed": False,
            "violations": ["base ref must be a non-empty Git commit reference"],
        }
    try:
        status_result = _git(["status", "--porcelain=v1", "-z", "--untracked-files=all"])
        if status_result.returncode != 0:
            return {
                "key": "key2_adversarial",
                "passed": False,
                "violations": [_git_failure(status_result, "status")],
            }
        status_entries = _parse_status_paths(status_result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return {"key": "key2_adversarial", "passed": False, "violations": [str(error)]}

    sensitive_status_paths = sorted({path for _, path in status_entries if is_sensitive_path(path)})
    if sensitive_status_paths:
        names = ", ".join(sensitive_status_paths)
        return {
            "key": "key2_adversarial",
            "passed": False,
            "violations": [f"Sensitive paths were excluded from audit: {names}"],
        }

    untracked_names = [path for status, path in status_entries if status == "??"]
    if base_ref is None:
        base_ref = "HEAD" if status_entries else "HEAD~1"

    print(f"\n🔑 KEY 2: Adversarial Review — Auditing diff against {base_ref}")
    print("-" * 50)

    try:
        resolved = _git(["rev-parse", "--verify", "--quiet", "--end-of-options", f"{base_ref}^{{commit}}"])
    except (OSError, subprocess.SubprocessError) as error:
        resolved = None
        error_detail = str(error)
    else:
        error_detail = _git_failure(resolved, "rev-parse") if resolved.returncode != 0 else ""
    if resolved is None or resolved.returncode != 0:
        return {
            "key": "key2_adversarial",
            "passed": False,
            "violations": [error_detail],
        }
    commit = resolved.stdout.strip()
    if not commit:
        return {
            "key": "key2_adversarial",
            "passed": False,
            "violations": ["Git rev-parse returned an empty commit id"],
        }

    try:
        changed_paths = _git(["diff", "--no-ext-diff", "--no-renames", "--name-only", "-z", commit, "--"])
        if changed_paths.returncode != 0:
            return {
                "key": "key2_adversarial",
                "passed": False,
                "violations": [_git_failure(changed_paths, "diff --name-only")],
            }
        sensitive_diff_paths = sorted({
            path for path in changed_paths.stdout.split("\0")
            if path and is_sensitive_path(path)
        })
        if sensitive_diff_paths:
            names = ", ".join(sensitive_diff_paths)
            return {
                "key": "key2_adversarial",
                "passed": False,
                "violations": [f"Sensitive paths were excluded from audit: {names}"],
            }

        diff = _git(["diff", "--no-ext-diff", "--no-renames", "--unified=0", commit, "--"])
        if diff.returncode != 0:
            return {
                "key": "key2_adversarial",
                "passed": False,
                "violations": [_git_failure(diff, "diff")],
            }
        added_all_lines = _diff_added_lines(diff.stdout)
        added_all_lines.extend(_read_untracked_lines(PROJECT_ROOT, untracked_names))
    except (OSError, subprocess.SubprocessError) as error:
        return {"key": "key2_adversarial", "passed": False, "violations": [str(error)]}

    if not diff.stdout.strip() and not untracked_names:
        print("  ❌ Empty audit: no tracked or untracked changes were reviewed")
        return {
            "key": "key2_adversarial",
            "passed": False,
            "violations": [],
            "note": "empty audit",
        }

    violations = []
    added_src_lines = [entry for entry in added_all_lines if not entry[0].startswith("test/")]

    for file, line in added_all_lines:
        if re.search(r"\b(it|test|describe)\.skip\(", line):
            violations.append(f"Test skipping detected in {file}: {line.strip()}")
        if re.search(r"\b(it|test|describe)\.only\(", line):
            violations.append(f"test.only() detected in {file}: {line.strip()}")

    for file, line in added_src_lines:
        if re.search(r"mock.*return.*true", line, re.IGNORECASE):
            violations.append(f"Mock returning hardcoded true in {file}: {line.strip()}")
        if re.search(r"console\.log.*pass", line, re.IGNORECASE):
            violations.append(f"Console.log('pass') in {file}: {line.strip()}")
        if re.search(r"catch\s*\([^)]*\)\s*\{\s*\}", line):
            violations.append(f"Empty catch block in {file}: {line.strip()}")

    for file, line in added_all_lines:
        if re.search(r"(?:BEGIN (?:RSA |DSA )?PRIVATE KEY)", line):
            violations.append(f"🔴 SECURITY: Private key in {file}")
        elif re.search(
            r"(?:password|secret|api_key|token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]",
            line,
            re.IGNORECASE,
        ) and not file.startswith("test/"):
            violations.append(f"🔴 SECURITY: Possible hardcoded secret in {file}")

    if violations:
        print("  Violations found:")
        for violation in violations:
            print(f"  ❌ {violation}")
    else:
        print("  ✅ No metric gaming or security violations detected")
    return {"key": "key2_adversarial", "passed": not violations, "violations": violations}


def write_event(results_dir, record, now, passed):
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y%m%d-%H%M%S-%f")
    suffix = uuid.uuid4().hex
    prefix = f"{stamp}-two-key-{'pass' if passed else 'fail'}-{suffix}"
    sequence = 0
    while True:
        name = f"{prefix}{f'-{sequence}' if sequence else ''}.json"
        event_file = results_dir / name
        try:
            with open(event_file, "x", encoding="utf-8") as destination:
                json.dump(record, destination, indent=2)
            return event_file
        except FileExistsError:
            sequence += 1


def run_full():
    print("=" * 60)
    print("  TWO-KEY VERIFICATION GATE")
    print("=" * 60)

    key1 = run_key1()
    key2 = run_key2()
    both_pass = key1["passed"] and key2["passed"]

    print("\n" + "=" * 60)
    print(f"  Key 1 (QA Gate):        {'✅ APPROVED' if key1['passed'] else '❌ REJECTED'}")
    print(f"  Key 2 (Adversarial):    {'✅ APPROVED' if key2['passed'] else '❌ REJECTED'}")
    print("-" * 60)
    print("  VERDICT: " + ("✅ APPROVED" if both_pass else "❌ REJECTED"))
    print("=" * 60)

    now = datetime.now(timezone.utc)
    record = {
        "event_id": f"twokey-{now.strftime('%Y%m%d%H%M%S%f')}-{uuid.uuid4().hex}",
        "timestamp": now.isoformat(),
        "agent": "two-key-gate",
        "type": "verification_passed" if both_pass else "verification_failed",
        "description": f"Two-Key verification {'passed' if both_pass else 'failed'}",
        "metadata": {"key1": key1, "key2": key2},
    }
    write_event(RESULTS_DIR, record, now, both_pass)
    return 0 if both_pass else 1


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in {"run", "key1", "key2"}:
        print(f"Usage: {sys.argv[0]} {{run|key1|key2}} [base_ref]")
        return 1
    if args[0] == "run":
        return run_full()
    if args[0] == "key1":
        result = run_key1()
    else:
        result = run_key2(args[1] if len(args) > 1 else None)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
