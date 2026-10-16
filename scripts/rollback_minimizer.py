#!/usr/bin/env python3
"""scripts/rollback_minimizer.py — DeepSWE Rollback Minimizer & Invariant Engine.

Implements the Gemini 4 Argon / DeepSWE pre-commit rollback defense principles:
- Patch blast-radius scoring and architectural boundary crossing detection.
- DeepSWE semantic invariant verification (no silent swallows, no test bypasses, no security leaks).
- Deterministic snapshot and safe-rollback compensation recovery.

Commands:
    analyze  [base_ref]       - Compute patch blast radius, boundary crossings, and risk rating
    verify   [base_ref]       - Verify DeepSWE behavioral and security invariants
    gate     [base_ref]       - Combined gate (blast radius + invariants) with exit code
    snapshot <name>           - Create deterministic pre-execution state snapshot
    restore  <name>           - Restore state snapshot on invariant failure
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SNAPSHOT_DIR = PROJECT_ROOT / "state" / "snapshots"

CRITICAL_PATHS = {
    "package.json",
    "src/version.ts",
    "src/index.ts",
    "src/state/schema.ts",
    "state/STATE.json",
    "scripts/verify.py",
    "scripts/two_key_gate.py",
    "scripts/killswitch.py",
}


def get_git_diff(base_ref: str = "HEAD") -> tuple[str, str]:
    """Retrieve stat and full diff content against base reference."""
    try:
        stat_res = subprocess.run(
            ["git", "diff", "--numstat", base_ref],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            shell=True,
        )
        diff_res = subprocess.run(
            ["git", "diff", base_ref],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            shell=True,
        )
        return stat_res.stdout, diff_res.stdout
    except Exception as e:
        return "", ""


def analyze_blast_radius(base_ref: str = "HEAD") -> dict:
    """Analyze patch blast radius and identify boundary crossings."""
    numstat_raw, _ = get_git_diff(base_ref)
    files_changed = 0
    lines_added = 0
    lines_deleted = 0
    critical_files_touched = []
    file_breakdown = []

    for line in numstat_raw.strip().splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            add_str, del_str, file_path = parts[0], parts[1], parts[2]
            added = int(add_str) if add_str.isdigit() else 0
            deleted = int(del_str) if del_str.isdigit() else 0
            files_changed += 1
            lines_added += added
            lines_deleted += deleted

            is_critical = any(file_path.endswith(cp) or file_path == cp for cp in CRITICAL_PATHS)
            if is_critical:
                critical_files_touched.append(file_path)

            file_breakdown.append({
                "path": file_path,
                "added": added,
                "deleted": deleted,
                "is_critical": is_critical,
            })

    total_lines = lines_added + lines_deleted
    # Blast radius formula: (total_lines * 0.1) + (files_changed * 2.0) + (critical * 5.0)
    blast_score = round((total_lines * 0.1) + (files_changed * 2.0) + (len(critical_files_touched) * 5.0), 2)

    if blast_score < 25.0:
        risk_rating = "LOW"
    elif blast_score < 60.0:
        risk_rating = "MODERATE"
    elif blast_score < 120.0:
        risk_rating = "HIGH"
    else:
        risk_rating = "EXTREME"

    return {
        "base_ref": base_ref,
        "files_changed": files_changed,
        "lines_added": lines_added,
        "lines_deleted": lines_deleted,
        "total_delta_lines": total_lines,
        "critical_boundary_crossings": critical_files_touched,
        "blast_score": blast_score,
        "risk_rating": risk_rating,
        "files": file_breakdown,
    }


def verify_invariants(base_ref: str = "HEAD") -> dict:
    """Verify DeepSWE behavioral invariants across changed content."""
    _, diff_content = get_git_diff(base_ref)
    violations = []

    current_file = ""
    added_src_lines: list[tuple[str, str]] = []
    added_all_lines: list[tuple[str, str]] = []

    for line in diff_content.splitlines():
        if line.startswith("diff --git"):
            parts = line.split()
            current_file = parts[-1].lstrip("b/") if len(parts) >= 4 else ""
        elif line.startswith("+") and not line.startswith("+++"):
            added_text = line[1:]
            added_all_lines.append((current_file, added_text))
            if not current_file.startswith("test/"):
                added_src_lines.append((current_file, added_text))

    for file, line in added_all_lines:
        if re.search(r"\b(it|test|describe)\.skip\(", line):
            violations.append(f"Invariant broken: Test skip detected in {file}: {line.strip()}")
        if re.search(r"\b(it|test|describe)\.only\(", line):
            violations.append(f"Invariant broken: Focused test.only detected in {file}: {line.strip()}")

    for file, line in added_src_lines:
        if re.search(r"mock.*return.*true", line, re.IGNORECASE):
            violations.append(f"Invariant broken: Hardcoded mock shortcut in {file}: {line.strip()}")
        if re.search(r"console\.log.*pass", line, re.IGNORECASE):
            violations.append(f"Invariant broken: Metric gaming print in {file}: {line.strip()}")
        if re.search(r"catch\s*\([^)]*\)\s*\{\s*\}", line):
            violations.append(f"Invariant broken: Silent error swallow in {file}: {line.strip()}")

    for file, line in added_all_lines:
        if re.search(r"(?:BEGIN (?:RSA |DSA )?PRIVATE KEY)", line):
            violations.append(f"Security invariant: Private key in {file}")
        elif re.search(r"(?:password|secret|api_key|token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]", line, re.IGNORECASE):
            if not file.startswith("test/"):
                violations.append(f"Security invariant: Unmasked credential in {file}")

    passed = len(violations) == 0
    return {
        "base_ref": base_ref,
        "passed": passed,
        "violations": violations,
        "checked_lines": len(added_all_lines),
    }


def create_snapshot(name: str) -> dict:
    """Create a deterministic snapshot of working directory state."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    target_dir = SNAPSHOT_DIR / name
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True)

    tracked_files = ["state/STATE.json", "state/HANDOFF.md", "package.json"]
    backed_up = []
    for tf in tracked_files:
        src = PROJECT_ROOT / tf
        if src.exists():
            dst = target_dir / tf
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            backed_up.append(tf)

    meta = {
        "snapshot_name": name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "files": backed_up,
    }
    with open(target_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return meta


def restore_snapshot(name: str) -> dict:
    """Restore a state snapshot on verification or invariant failure."""
    target_dir = SNAPSHOT_DIR / name
    if not target_dir.exists():
        raise FileNotFoundError(f"Snapshot '{name}' not found in {SNAPSHOT_DIR}")

    with open(target_dir / "meta.json", "r", encoding="utf-8") as f:
        meta = json.load(f)

    restored = []
    for tf in meta.get("files", []):
        src = target_dir / tf
        dst = PROJECT_ROOT / tf
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            restored.append(tf)

    return {
        "status": "RESTORED",
        "snapshot_name": name,
        "restored_files": restored,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(description="DeepSWE Rollback Minimizer & Invariant Engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_p = subparsers.add_parser("analyze", help="Analyze blast radius")
    analyze_p.add_argument("base_ref", nargs="?", default="HEAD", help="Base git reference")

    verify_p = subparsers.add_parser("verify", help="Verify DeepSWE behavioral invariants")
    verify_p.add_argument("base_ref", nargs="?", default="HEAD", help="Base git reference")

    gate_p = subparsers.add_parser("gate", help="Run combined rollback minimizer gate")
    gate_p.add_argument("base_ref", nargs="?", default="HEAD", help="Base git reference")

    snap_p = subparsers.add_parser("snapshot", help="Create pre-execution state snapshot")
    snap_p.add_argument("name", help="Snapshot identifier")

    rest_p = subparsers.add_parser("restore", help="Restore state snapshot")
    rest_p.add_argument("name", help="Snapshot identifier")

    args = parser.parse_args()

    if args.command == "analyze":
        res = analyze_blast_radius(args.base_ref)
        print(json.dumps(res, indent=2))
        return 0

    elif args.command == "verify":
        res = verify_invariants(args.base_ref)
        print(json.dumps(res, indent=2))
        return 0 if res["passed"] else 1

    elif args.command == "gate":
        analysis = analyze_blast_radius(args.base_ref)
        invariants = verify_invariants(args.base_ref)
        gate_passed = invariants["passed"] and analysis["risk_rating"] != "EXTREME"
        verdict = {
            "gate_passed": gate_passed,
            "blast_analysis": analysis,
            "invariant_verification": invariants,
            "recommendation": "PROCEED" if gate_passed else "ROLLBACK",
        }
        print(json.dumps(verdict, indent=2))
        return 0 if gate_passed else 1

    elif args.command == "snapshot":
        res = create_snapshot(args.name)
        print(json.dumps(res, indent=2))
        return 0

    elif args.command == "restore":
        res = restore_snapshot(args.name)
        print(json.dumps(res, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
