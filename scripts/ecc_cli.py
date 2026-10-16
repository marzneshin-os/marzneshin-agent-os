#!/usr/bin/env python3
"""ECC Universal Agent Harness & AgentShield CLI.

Operational CLI tool for Marzneshin Agent OS developers and autonomous agents:
- `status`: Display overall health, instincts count, and latest security report.
- `scan`: Run AgentShield audit across workspace files, configs, and rules.
- `instincts`: List, query, or record continuous learning instincts.
- `sync`: Verify and audit cross-agentic harness configuration parity.
- `audit`: Full readiness scorecard across harnesses, tools, and security rules.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(WORKSPACE_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))

from lib.ecc_harness import AgentShieldScanner, HarnessAudit, InstinctStore


def cmd_status(args: argparse.Namespace) -> int:
    store = InstinctStore(repo_root=WORKSPACE_ROOT)
    instincts = store.query()
    reports_file = WORKSPACE_ROOT / "state" / "reports" / "agentshield_latest.json"

    latest_scan = "None"
    scan_status = "N/A"
    if reports_file.exists():
        try:
            r_data = json.loads(reports_file.read_text(encoding="utf-8"))
            scan_status = "PASSED" if r_data.get("passed") else "FAILED"
            latest_scan = r_data.get("timestamp", "Unknown")
        except Exception:
            pass

    auditor = HarnessAudit(repo_root=WORKSPACE_ROOT)
    audit_report = auditor.audit()

    print("================================================================")
    print("  Everything Claude Code (ECC) Universal Agent Harness Status  ")
    print("================================================================")
    print(f"Instincts Cataloged   : {len(instincts)} active heuristics")
    print(f"Latest AgentShield Scan: {scan_status} ({latest_scan})")
    print(f"Cross-Harness Parity  : {len(audit_report.harnesses_detected)}/{len(auditor.REQUIRED_SURFACES)} harnesses aligned")
    for h, active in audit_report.status.items():
        mark = "?" if active else "?"
        print(f"  [{mark}] {h.capitalize():12}: {'Active' if active else 'Missing rules'}")
    print("================================================================")
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    scanner = AgentShieldScanner(repo_root=WORKSPACE_ROOT)
    targets = args.targets.split(",") if args.targets else None
    report = scanner.scan_workspace(targets=targets, strict=args.strict)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.passed else 1

    status_str = "PASSED (Safe)" if report.passed else "FAILED (Vulnerabilities Detected)"
    print(f"AgentShield Security Scan Verdict: {status_str}")
    print(f"Findings Breakdown: CRITICAL={report.summary.get('CRITICAL',0)} | HIGH={report.summary.get('HIGH',0)} | MEDIUM={report.summary.get('MEDIUM',0)} | LOW={report.summary.get('LOW',0)}")

    if report.findings:
        print("\nSecurity Findings:")
        for f in report.findings:
            print(f"  [{f.severity}] {f.rule_id} @ {f.file}:{f.line}")
            print(f"    Issue: {f.description}")
            print(f"    Fix  : {f.remediation}\n")

    return 0 if report.passed else 1


def cmd_instincts(args: argparse.Namespace) -> int:
    store = InstinctStore(repo_root=WORKSPACE_ROOT)

    if args.action == "learn":
        if not args.trigger or not args.rule_action:
            print("Error: --trigger and --rule-action are required to learn an instinct.", file=sys.stderr)
            return 1
        domains = args.domain.split(",") if args.domain else ["general"]
        inst = store.learn(
            trigger=args.trigger,
            action=args.rule_action,
            rationale=args.rationale or "User provided via CLI",
            domain=domains,
            confidence=args.confidence or 0.8,
            provenance="cli_operator",
        )
        print(f"Learned instinct [{inst.id}]: {inst.action} (Confidence: {inst.confidence})")
        return 0

    elif args.action == "boost":
        if not args.id:
            print("Error: --id is required to boost an instinct.", file=sys.stderr)
            return 1
        inst = store.update_confidence(args.id, success=args.success)
        if inst:
            print(f"Updated instinct [{inst.id}]: Confidence now {inst.confidence} (Success count: {inst.success_count}/{inst.executions_count})")
            return 0
        else:
            print(f"Instinct {args.id} not found.", file=sys.stderr)
            return 1

    # Default: query / list
    results = store.query(query_str=args.query, domain=args.domain)
    if args.json:
        print(json.dumps([r.to_dict() for r in results], indent=2))
        return 0

    print(f"Total Instincts Found: {len(results)}\n")
    for i in results:
        print(f"[{i.id}] (Confidence: {i.confidence:.2f} | Domain: {','.join(i.domain)})")
        print(f"  Trigger  : {i.trigger}")
        print(f"  Action   : {i.action}")
        print(f"  Rationale: {i.rationale}\n")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    auditor = HarnessAudit(repo_root=WORKSPACE_ROOT)
    report = auditor.audit()
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.ok else 1

    print("Harness Synchronization Report:")
    print(report.details)
    for h, active in report.status.items():
        print(f"  - {h.capitalize():12}: {'IN SYNC' if active else 'MISSING'}")
    if report.missing_rules:
        print("\nMissing Surfaces:")
        for m in report.missing_rules:
            print(f"  * {m}")
    return 0 if report.ok else 1


def cmd_audit(args: argparse.Namespace) -> int:
    # Full readiness scorecard
    cmd_status(args)
    print("\n--- Running AgentShield Security Gate ---")
    scanner = AgentShieldScanner(repo_root=WORKSPACE_ROOT)
    sec_report = scanner.scan_workspace(strict=False)
    print(f"AgentShield Verdict: {'PASSED' if sec_report.passed else 'FAILED'}")
    return 0 if sec_report.passed else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="ECC Universal Agent Harness & AgentShield CLI")
    subparsers = parser.add_subparsers(dest="command")

    # status
    subparsers.add_parser("status", help="Show ECC harness status")

    # scan
    scan_p = subparsers.add_parser("scan", help="Run AgentShield security audit")
    scan_p.add_argument("--targets", help="Comma-separated paths to scan")
    scan_p.add_argument("--strict", action="store_true", help="Fail on MEDIUM severity")
    scan_p.add_argument("--json", action="store_true", help="Emit JSON output")

    # instincts
    inst_p = subparsers.add_parser("instincts", help="Query or manage instincts")
    inst_p.add_argument("action", nargs="?", default="list", choices=["list", "learn", "boost"])
    inst_p.add_argument("--query", help="Search trigger/action text")
    inst_p.add_argument("--domain", help="Filter by domain category")
    inst_p.add_argument("--trigger", help="Trigger pattern for learn")
    inst_p.add_argument("--rule-action", help="Action guideline for learn")
    inst_p.add_argument("--rationale", help="Rationale explanation")
    inst_p.add_argument("--confidence", type=float, default=0.8, help="Confidence score")
    inst_p.add_argument("--id", help="Instinct ID for boost")
    inst_p.add_argument("--success", action="store_true", default=True, help="Mark success for boost")
    inst_p.add_argument("--json", action="store_true", help="Emit JSON output")

    # sync
    sync_p = subparsers.add_parser("sync", help="Check cross-agent harness sync")
    sync_p.add_argument("--json", action="store_true", help="Emit JSON output")

    # audit
    subparsers.add_parser("audit", help="Full readiness scorecard")

    args = parser.parse_args()
    if not args.command or args.command == "status":
        return cmd_status(args)
    elif args.command == "scan":
        return cmd_scan(args)
    elif args.command == "instincts":
        return cmd_instincts(args)
    elif args.command == "sync":
        return cmd_sync(args)
    elif args.command == "audit":
        return cmd_audit(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
