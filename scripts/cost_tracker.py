#!/usr/bin/env python3
"""Marzneshin OS — Cost & Budget Governance Tracker (Jev Meter).
Provides /cost report, stage budget monitoring, and hard-stop enforcement.
"""
import sys
import json
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = REPO_ROOT / 'state'
TELEMETRY_FILE = STATE_DIR / 'claude_session_telemetry.json'
STAGE_COSTS_FILE = STATE_DIR / 'cost_stages.json'
HANDOFFS_LOG = REPO_ROOT / 'logs' / 'handoffs.log'

STAGE_BUDGETS = {
    'ingest': 0.10,
    'plan': 0.25,
    'execute': 1.00,
    'verify': 0.35,
    'gate': 0.15,
    'commit': 0.15
}
TOTAL_TASK_BUDGET = 2.00

def get_telemetry() -> dict:
    if TELEMETRY_FILE.exists():
        try:
            return json.loads(TELEMETRY_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {}

def get_stage_data() -> dict:
    if STAGE_COSTS_FILE.exists():
        try:
            return json.loads(STAGE_COSTS_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {'current_stage': 'execute', 'stages': {}}

def cmd_report():
    telemetry = get_telemetry()
    stage_data = get_stage_data()

    total_cost = telemetry.get('cost', {}).get('total_cost_usd', 0.0)
    in_tok = telemetry.get('context_window', {}).get('total_input_tokens', 0)
    out_tok = telemetry.get('context_window', {}).get('total_output_tokens', 0)
    used_pct = telemetry.get('context_window', {}).get('used_percentage', 0.0)
    total_tokens = in_tok + out_tok

    pct_budget = (total_cost / TOTAL_TASK_BUDGET) * 100 if TOTAL_TASK_BUDGET > 0 else 0
    rem_budget = max(0.0, TOTAL_TASK_BUDGET - total_cost)

    print("=" * 72)
    print("⚡ Marzneshin Agent OS — Claude Code Budget & Cost Tracker (Jev Board)")
    print("=" * 72)
    print(f"Session Spend:      ${total_cost:.2f} / ${TOTAL_TASK_BUDGET:.2f} ({pct_budget:.1f}% of task budget)")
    print(f"Remaining Budget:   ${rem_budget:.2f}")
    print(f"Total Tokens:       {total_tokens:,} tokens (Context Used: {used_pct:.1f}%)")
    print(f"Active Stage:       [{stage_data.get('current_stage', 'execute').upper()}]")
    print("-" * 72)
    print(f"{'STAGE':<12} {'LIMIT':<10} {'SPENT':<10} {'STATUS':<12} {'REMAINING':<10}")
    print("-" * 72)

    stages = stage_data.get('stages', {})
    for st_name, limit in STAGE_BUDGETS.items():
        st_spent = stages.get(st_name, {}).get('cost', 0.0)
        rem = max(0.0, limit - st_spent)
        if st_spent > limit:
            status = "🔴 OVER BUDGET"
        elif st_spent >= (limit * 0.8):
            status = "🟡 WARN (>80%)"
        else:
            status = "🟢 OK"
        print(f"{st_name.capitalize():<12} ${limit:<9.2f} ${st_spent:<9.2f} {status:<12} ${rem:<9.2f}")

    print("-" * 72)
    print("RECENT AGENT HANDOFFS (from logs/handoffs.log):")
    if HANDOFFS_LOG.exists():
        lines = [line.strip() for line in HANDOFFS_LOG.read_text(encoding='utf-8').splitlines() if line.strip() and not line.startswith('#')]
        for line in lines[-5:]:
            print(f"  → {line}")
        if not lines:
            print("  (No subagent handoffs recorded yet)")
    else:
        print("  (logs/handoffs.log not found)")
    print("=" * 72)

def cmd_set_stage(stage_name: str):
    stage_name = stage_name.lower()
    if stage_name not in STAGE_BUDGETS:
        print(f"Unknown stage: {stage_name}. Choose from: {list(STAGE_BUDGETS.keys())}")
        sys.exit(1)
    
    stage_data = get_stage_data()
    stage_data['current_stage'] = stage_name
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_COSTS_FILE.write_text(json.dumps(stage_data, indent=2), encoding='utf-8')
    print(f"✓ Active stage set to: [{stage_name.upper()}] (Limit: ${STAGE_BUDGETS[stage_name]:.2f})")

def cmd_check():
    telemetry = get_telemetry()
    stage_data = get_stage_data()
    total_cost = telemetry.get('cost', {}).get('total_cost_usd', 0.0)
    current_stage = stage_data.get('current_stage', 'execute')
    stage_spent = stage_data.get('stages', {}).get(current_stage, {}).get('cost', 0.0)
    stage_limit = STAGE_BUDGETS.get(current_stage, 1.00)

    if total_cost >= TOTAL_TASK_BUDGET:
        print(f"🛑 HARD STOP: Task budget exceeded! Spend: ${total_cost:.2f} >= Budget: ${TOTAL_TASK_BUDGET:.2f}")
        sys.exit(1)
    
    if stage_spent > stage_limit:
        print(f"🛑 HARD STOP: Stage [{current_stage.upper()}] budget exceeded! Spend: ${stage_spent:.2f} > Limit: ${stage_limit:.2f}")
        sys.exit(1)

    print("🟢 Budget check passed.")
    sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description="Marzneshin OS Cost Tracker")
    subparsers = parser.add_subparsers(dest="command")
    
    subparsers.add_parser("report", help="Show budget & cost report")
    stage_parser = subparsers.add_parser("stage", help="Set active stage")
    stage_parser.add_argument("name", help="Stage name (ingest, plan, execute, verify, gate, commit)")
    subparsers.add_parser("check", help="Check budget limits (exit 1 if exceeded)")

    args = parser.parse_args()
    if args.command == "report" or not args.command:
        cmd_report()
    elif args.command == "stage":
        cmd_set_stage(args.name)
    elif args.command == "check":
        cmd_check()

if __name__ == '__main__':
    main()
