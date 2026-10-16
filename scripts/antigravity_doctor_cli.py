#!/usr/bin/env python3
"""Antigravity Doctor CLI — Diagnostics, Credential Cleaner & Environment Repair."""

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(1, str(REPO / "scripts"))

from scripts.lib.antigravity_doctor import AntigravityDoctor


def main() -> int:
    parser = argparse.ArgumentParser(description="Antigravity Account Doctor & Health Recovery")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # diagnose
    diag_p = subparsers.add_parser("diagnose", help="Run full diagnostic matrix on current session")
    diag_p.add_argument("--token", type=str, default=None, help="Raw JSON token string or path to inspect")
    diag_p.add_argument("--json", action="store_true", help="Output raw JSON")

    # clean
    clean_p = subparsers.add_parser("clean", help="Purge stale Antigravity credentials and locks")
    clean_p.add_argument("--dry-run", action="store_true", help="Simulate without deleting")
    clean_p.add_argument("--json", action="store_true", help="Output raw JSON")

    # repair
    rep_p = subparsers.add_parser("repair", help="Full environment recovery & re-authentication guidance")
    rep_p.add_argument("--dry-run", action="store_true", help="Simulate repair actions")
    rep_p.add_argument("--json", action="store_true", help="Output raw JSON")

    # check-email
    check_p = subparsers.add_parser("check-email", help="Check eligibility status for an email address")
    check_p.add_argument("email", type=str, help="Email address to evaluate")
    check_p.add_argument("--json", action="store_true", help="Output raw JSON")

    # status
    stat_p = subparsers.add_parser("status", help="Concise one-line health status")
    stat_p.add_argument("--json", action="store_true", help="Output raw JSON")

    args = parser.parse_args()
    doctor = AntigravityDoctor()

    if args.command == "diagnose":
        token_content = args.token
        if token_content and Path(token_content).is_file():
            token_content = Path(token_content).read_text(encoding="utf-8")
        diag = doctor.diagnose(token_str=token_content)
        if args.json:
            print(json.dumps(diag.to_dict(), indent=2))
        else:
            print(f"\n╭─────────────────────────────────────────────────────────────╮")
            print(f"│ 🩺 Antigravity Account Doctor Diagnostic Report             │")
            print(f"╰─────────────────────────────────────────────────────────────╯")
            print(f" Overall Status:      {diag.status}")
            print(f" Operating System:    {diag.platform}")
            print(f" Active Account:      {diag.active_email or 'Not Detected'}")
            print(f" Workspace Domain:    {diag.is_workspace_account}")
            print(f" Credential Store:    {diag.credential_store_status.get('targets', [])}")
            print(f" Token Valid:         {diag.session_token_status.get('valid_json', False)}")
            print(f" Token Expired:       {diag.session_token_status.get('expired', False)}")
            print(f" Stale Locks Found:   {len(diag.cache_status.get('lock_files', []))}")
            if diag.issues:
                print(f"\n [!] Identified Issues ({len(diag.issues)}):")
                for iss in diag.issues:
                    print(f"   • [{iss['severity']}] {iss['code']}: {iss['message']}")
                    print(f"     Recommendation: {iss['recommendation']}")
            if diag.next_actions:
                print(f"\n [>] Recommended Actions:")
                for act in diag.next_actions:
                    print(f"   • {act}")
            print()
        return 0 if diag.status in ("HEALTHY", "WARNING") else 1

    elif args.command == "clean":
        res = doctor.clean(dry_run=args.dry_run)
        if args.json:
            print(json.dumps(res.to_dict(), indent=2))
        else:
            prefix = "[DRY-RUN] " if args.dry_run else ""
            print(f"\n🧹 {prefix}Antigravity Cleaner:")
            print(f" Removed Credentials: {res.removed_credentials}")
            print(f" Cleared Caches:      {res.cleared_caches}")
            if res.errors:
                print(f" Errors encountered:  {res.errors}")
            print(f" Status:              {'SUCCESS' if res.ok else 'FAILED'}\n")
        return 0 if res.ok else 1

    elif args.command == "repair":
        res = doctor.repair(dry_run=args.dry_run)
        if args.json:
            print(json.dumps(res.to_dict(), indent=2))
        else:
            prefix = "[DRY-RUN] " if args.dry_run else ""
            print(f"\n🔧 {prefix}Antigravity Environment Repair:")
            print(f" Credential Clean:    {'OK' if res.clean_result.get('ok') else 'FAIL'}")
            print(f"\nNext Authentication Steps:")
            for k, step in res.reauth_guidance.items():
                print(f" • {step}")
            print()
        return 0 if res.ok else 1

    elif args.command == "check-email":
        is_ws = doctor.is_workspace_domain(args.email)
        out = {
            "email": args.email,
            "is_workspace": is_ws,
            "eligible": not is_ws,
            "recommendation": (
                "Google Workspace accounts are ineligible for Antigravity individual tier. Use personal @gmail.com."
                if is_ws
                else "Personal Google account is supported."
            ),
        }
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            print(f"\nAccount:        {args.email}")
            print(f"Domain Type:    {'Workspace / Managed' if is_ws else 'Personal Gmail'}")
            print(f"Eligible:       {'NO (403 risk)' if is_ws else 'YES'}")
            print(f"Details:        {out['recommendation']}\n")
        return 1 if is_ws else 0

    elif args.command == "status":
        diag = doctor.diagnose()
        if args.json:
            print(json.dumps({"status": diag.status, "email": diag.active_email}, indent=2))
        else:
            print(f"Antigravity Status: {diag.status} (Account: {diag.active_email or 'None'})")
        return 0 if diag.status == "HEALTHY" else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
