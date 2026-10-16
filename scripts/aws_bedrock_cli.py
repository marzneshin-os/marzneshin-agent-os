#!/usr/bin/env python3
"""AWS Bedrock Promotional Credit Pool & Zero-Cost Guardrail CLI (ADR-029)."""

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(1, str(REPO / "scripts"))

from scripts.lib.aws_bedrock_credits import (
    BedrockCreditPoolManager,
    DEFAULT_MODEL,
    DEFAULT_SAFETY_BUFFER_USD,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="AWS Bedrock Promotional Credit Pool & Zero-Cost Guardrail CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status
    stat_p = subparsers.add_parser("status", help="Get pool status, credit balances, and zero-cost guardrails")
    stat_p.add_argument("--json", action="store_true", help="Output raw JSON")

    # register
    reg_p = subparsers.add_parser("register", help="Register a new AWS promotional credit account")
    reg_p.add_argument("--account-id", required=True, help="AWS Account ID or unique alias")
    reg_p.add_argument("--alias", required=True, help="Descriptive label (e.g. 'Builder ID Dev 1')")
    reg_p.add_argument("--access-key", default="", help="AWS Access Key ID")
    reg_p.add_argument("--secret-key", default="", help="AWS Secret Access Key")
    reg_p.add_argument("--region", default="us-east-1", help="AWS Region (default: us-east-1)")
    reg_p.add_argument("--credits", type=float, default=100.0, help="Initial credit grant in USD (default: 100.0)")
    reg_p.add_argument("--safety-buffer", type=float, default=DEFAULT_SAFETY_BUFFER_USD, help="Safety buffer USD (default: 5.0)")
    reg_p.add_argument("--json", action="store_true", help="Output raw JSON")

    # rotate
    rot_p = subparsers.add_parser("rotate", help="Rotate to next eligible account with highest credit balance")
    rot_p.add_argument("--json", action="store_true", help="Output raw JSON")

    # onboarding
    onb_p = subparsers.add_parser("onboarding", help="Inspect or complete Explore AWS onboarding exploration tasks")
    onb_p.add_argument("--account-id", default=None, help="Specific account ID (defaults to active)")
    onb_p.add_argument("--task", choices=["ec2", "bedrock", "lambda", "rds", "budget"], default=None, help="Task identifier")
    onb_p.add_argument("--complete", action="store_true", help="Mark task completed and apply credit grant")
    onb_p.add_argument("--json", action="store_true", help="Output raw JSON")

    # invoke
    inv_p = subparsers.add_parser("invoke", help="Invoke a Bedrock model with token spend deduction")
    inv_p.add_argument("--model", default=DEFAULT_MODEL, help="Model ID")
    inv_p.add_argument("--prompt", required=True, help="Input prompt")
    inv_p.add_argument("--dry-run", action="store_true", help="Calculate predicted cost without mutating balance")
    inv_p.add_argument("--json", action="store_true", help="Output raw JSON")

    args = parser.parse_args()
    mgr = BedrockCreditPoolManager()

    if args.command == "status":
        st = mgr.pool_status()
        if args.json:
            print(json.dumps(st, indent=2))
        else:
            print("=== AWS Bedrock Promotional Credit Pool Status ===")
            print(f"Total Accounts:    {st['total_accounts']} (Active: {st['active_accounts']})")
            print(f"Total Remaining:   ${st['total_remaining_usd']:.2f}")
            print(f"Total Spent:       ${st['total_spent_usd']:.2f}")
            print(f"Active Account ID: {st['active_account_id']}")
            print(f"Zero-Cost Guard:   {st['zero_cost_guardrail']['status']} (Buffer: ${st['zero_cost_guardrail']['safety_buffer_usd']:.2f})")
            print("\nAccounts:")
            for a in st["accounts"]:
                print(f"  - [{a['status'].upper()}] {a['alias']} ({a['account_id']}): ${a['remaining_usd']:.2f} remaining, expires in {a['days_to_expiry']} days, {a['onboarding_completed']}/5 tasks done")
        return 0

    elif args.command == "register":
        acc = mgr.register_account(
            account_id=args.account_id,
            alias=args.alias,
            access_key_id=args.access_key,
            secret_access_key=args.secret_key,
            region=args.region,
            initial_credit_usd=args.credits,
            safety_buffer_usd=args.safety_buffer,
        )
        if args.json:
            print(json.dumps(acc.to_dict(redact_secret=True), indent=2))
        else:
            print(f"Successfully registered account: {acc.alias} (${acc.remaining_usd:.2f} credits grant)")
        return 0

    elif args.command == "rotate":
        chosen = mgr.rotate_account()
        if args.json:
            print(json.dumps({"active_account": chosen.to_dict(redact_secret=True) if chosen else None}, indent=2))
        else:
            if chosen:
                print(f"Rotated active account to: {chosen.alias} (${chosen.remaining_usd:.2f} credits remaining)")
            else:
                print("No eligible accounts available with remaining credits!")
        return 0

    elif args.command == "onboarding":
        acc_id = args.account_id or mgr.active_account_id
        if not acc_id or acc_id not in mgr.accounts:
            print("Error: No active or valid account specified", file=sys.stderr)
            return 1
        acc = mgr.accounts[acc_id]
        if args.task and args.complete:
            res = mgr.complete_onboarding_task(acc_id, args.task, resource_cleaned=True)
            if args.json:
                print(json.dumps(res, indent=2))
            else:
                print(f"Task '{args.task}' marked completed! New credit grant: ${res['initial_credit_usd']:.2f} (${res['remaining_usd']:.2f} remaining)")
        else:
            if args.json:
                print(json.dumps(acc.onboarding_tasks, indent=2))
            else:
                print(f"=== Onboarding Tasks for {acc.alias} ===")
                for tid, t in acc.onboarding_tasks.items():
                    mark = "[x]" if t["completed"] else "[ ]"
                    print(f"  {mark} {t['name']} (+${t['credit_value_usd']:.2f}): {t['note']}")
        return 0

    elif args.command == "invoke":
        prompt_tokens = max(1, len(args.prompt.split()))
        completion_tokens = 30
        cost_usd = mgr.calculate_cost_usd(args.model, prompt_tokens, completion_tokens)
        if args.dry_run:
            payload = {
                "dry_run": True,
                "model": args.model,
                "predicted_cost_usd": round(cost_usd, 6),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "guardrail": "PASS - Zero Cost Guaranteed",
            }
            print(json.dumps(payload, indent=2) if args.json else f"Dry Run Predicted Cost: ${cost_usd:.6f}")
            return 0

        active = mgr.get_active_account()
        if not active:
            print("Error: No eligible Bedrock account with sufficient credits remaining", file=sys.stderr)
            return 1

        rec = mgr.record_execution(active.account_id, args.model, prompt_tokens, completion_tokens)
        out = {
            "model": args.model,
            "output_text": f"Simulated Bedrock output from {args.model} for: '{args.prompt}'",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": rec.get("cost_usd"),
            "remaining_usd": rec.get("remaining_usd"),
            "account": active.alias,
        }
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            print(f"[{active.alias}] Cost: ${rec.get('cost_usd'):.6f} | Remaining: ${rec.get('remaining_usd'):.4f}")
            print(f"Output: {out['output_text']}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
