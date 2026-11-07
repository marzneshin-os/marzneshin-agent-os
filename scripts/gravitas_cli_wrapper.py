#!/usr/bin/env python3
"""
Marzneshin Agent OS — Gravitas Reliability Integration
Provides programmatic Python bindings and unified CLI for Gravitas
runtime operations, policy decisions, validator escalation, and session auditing.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
GRAVITAS_ENGINE = REPO_ROOT / "engines" / "gravitas"
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
VENV_GRAVITAS = REPO_ROOT / ".venv" / "bin" / "gravitas"


def get_gravitas_cmd() -> List[str]:
    """Resolve the executable path to gravitas CLI."""
    if VENV_GRAVITAS.exists():
        return [str(VENV_GRAVITAS)]
    # Fallback to python -m gravitas_cli
    python_bin = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
    return [python_bin, str(GRAVITAS_ENGINE / "gravitas_cli.py")]


def run_doctor() -> Dict[str, Any]:
    """Run Gravitas doctor diagnostic and return checks dict."""
    cmd = get_gravitas_cmd() + ["doctor"]
    result = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    if result.returncode == 0:
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"status": "ok", "raw": result.stdout}
    return {"status": "error", "code": result.returncode, "error": result.stderr or result.stdout}


def decide_policy(signals: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compute planning and verification policy record for a task."""
    cmd = get_gravitas_cmd() + ["decide", "--signals", json.dumps(signals or {})]
    result = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    if result.returncode == 0:
        return json.loads(result.stdout)
    raise RuntimeError(f"Gravitas decide failed: {result.stderr or result.stdout}")


def discover_validators(root: Optional[Path] = None) -> Dict[str, Any]:
    """Discover repo-aware validators and escalation plan."""
    target_root = str(root or REPO_ROOT)
    cmd = get_gravitas_cmd() + ["validators", "--root", target_root]
    result = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    if result.returncode == 0:
        return json.loads(result.stdout)
    raise RuntimeError(f"Gravitas validators failed: {result.stderr or result.stdout}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Marzneshin Gravitas Integration CLI")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    sub.add_parser("doctor", help="Check Gravitas runtime integrity")
    
    decide_p = sub.add_parser("decide", help="Compute adaptive planning policy")
    decide_p.add_argument("--signals", type=str, default="{}", help="JSON signals dictionary")

    val_p = sub.add_parser("validators", help="Discover repository validators")
    val_p.add_argument("--root", type=str, default=str(REPO_ROOT), help="Project root directory")

    status_p = sub.add_parser("status", help="List active Gravitas sessions")

    args = parser.parse_args()

    if args.subcommand == "doctor":
        doc = run_doctor()
        print(json.dumps(doc, indent=2))
        return 0 if doc.get("skill") and doc.get("hooks") else 1

    elif args.subcommand == "decide":
        signals = json.loads(args.signals)
        policy = decide_policy(signals)
        print(json.dumps(policy, indent=2))
        return 0

    elif args.subcommand == "validators":
        vals = discover_validators(Path(args.root))
        print(json.dumps(vals, indent=2))
        return 0

    elif args.subcommand == "status":
        cmd = get_gravitas_cmd() + ["status"]
        result = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
        print(result.stdout)
        return result.returncode

    return 0


if __name__ == "__main__":
    sys.exit(main())
