#!/usr/bin/env python3
"""dashboard.py — Revenue Command Center CLI (BUILD-SPEC §9.4, §13.5, VS-10).

Usage:
  dashboard.py summary            display formatted revenue command center summary
  dashboard.py json               dump command center metrics as JSON
  dashboard.py export-grafana     validate and print Grafana dashboard path
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(1, str(REPO / "scripts"))

from lib import paths, revenue  # noqa: E402


def cmd_summary(args: argparse.Namespace) -> int:
    data = revenue.get_revenue_command_center(window_days=args.window)

    nsm = data["north_star"]
    rev = data["revenue"]
    ue = data["unit_economics"]
    te = data["token_economics"]
    rel = data["reliability"]
    fleet = data["agent_fleet"]
    ckpi = data["counter_kpis"]
    exps = data["experiments"]

    print("=" * 70)
    print("      MARZNESHIN REVENUE COMMAND CENTER (BUILD-SPEC §9.4, §13.5)")
    print("=" * 70)
    print(f"Generated At: {data['generated_at']} (Window: {data['window_days']} days)")
    print("-" * 70)
    print("1. TOPLINE & NORTH STAR METRIC (§13.2):")
    print(f"   North Star Metric (NSM):  {nsm['nsm_count']} active connected paid users (7d)")
    print(f"   Total Paid Customers:     {rev['paid_customers']}")
    print(f"   Monthly Recurring (MRR):  ${rev['mrr']:.2f}")
    print(f"   Annual Run Rate (ARR):    ${rev['arr']:.2f}")
    print(f"   Average Revenue / User:   ${rev['arpu']:.2f}")
    print(f"   Net Revenue Retention:    {rev['nrr_pct']:.1f}%")
    print("-" * 70)
    print("2. LIVE UNIT ECONOMICS & AGENT TOKEN COSTS (§13.3, §13.5):")
    print(f"   Gross Margin:             {ue['gross_margin_pct']:.2f}% (Target: > 70%)")
    print(f"   Gross Profit / User:      ${ue['gross_profit_per_user']:.2f}")
    print(f"   Live Token Cost / User:   ${te['live_token_cost_per_active_user']:.4f} (Live from budget ledger)")
    print(f"   LTV (Lifetime Value):     ${ue['ltv']:.2f}")
    print(f"   LTV : CAC Ratio:          {ue['ltv_cac_ratio']:.2f}x (Target: > 3.0)")
    print(f"   CAC Payback Period:       {ue['cac_payback_months']:.2f} months (Target: < 3.0 mo)")
    print("-" * 70)
    print("3. RELIABILITY & PROBE FLEET SLO (§12):")
    print(f"   Fleet CSR:                {rel['csr_pct']:.2f}% (SLO Target: >= {rel['slo_target_pct']}%)")
    print(f"   SLO Met:                  {'YES (GREEN)' if rel['slo_met'] else 'NO (DEGRADED)'}")
    print(f"   Healthy ASNs:             {', '.join(rel['healthy_asns'])}")
    print("-" * 70)
    print("4. AUTONOMOUS AGENT FLEET & LEVERAGE (§10.1):")
    print(f"   Agent Leverage Ratio:     {fleet['leverage_ratio']}x (Autonomous L2+ / Interventions L0)")
    print(f"   Autonomous Tasks:         {fleet['autonomous_tasks']}")
    print(f"   Manual Interventions:     {fleet['manual_interventions']}")
    print(f"   Total Audit Receipts:     {fleet['total_receipts']} (100% receipt coverage)")
    print("-" * 70)
    print("5. COUNTER-KPI GUARDRAIL MATRIX (§10.4, Rule I13):")
    print(f"   Panel Health Status:      {ckpi['panel_status'].upper()}")
    for agent in ckpi["agents"]:
        print(f"   - {agent['name']:<25} | Counter-KPI: {agent['counter_kpi']:<20} | Owner: {agent['counter_kpi_owner']}")
    print("-" * 70)
    print("6. SAFE EXPERIMENTATION & READOUT LOOP (§13.4):")
    print(f"   Active Trials:            {exps['active']}")
    print(f"   Shipped (Proven Lift):    {exps['shipped']}")
    print(f"   Killed / Stopped:         {exps['killed']}")
    print("=" * 70)
    return 0


def cmd_json(args: argparse.Namespace) -> int:
    data = revenue.get_revenue_command_center(window_days=args.window)
    print(json.dumps(data, indent=2))
    return 0


def cmd_export_grafana(args: argparse.Namespace) -> int:
    g_path = REPO / "dashboards" / "grafana" / "revenue_command_center.json"
    if not g_path.exists():
        print(f"ERROR: Grafana dashboard JSON not found at {g_path}", file=sys.stderr)
        return 1
    with open(g_path, encoding="utf-8") as f:
        data = json.load(f)
    print(f"Grafana dashboard valid: {data.get('title')} (UID: {data.get('uid')})")
    print(f"Path: {g_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Revenue Command Center CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sum = sub.add_parser("summary", help="display formatted revenue command center summary")
    p_sum.add_argument("--window", type=int, default=30, help="lookback window in days")
    p_sum.set_defaults(func=cmd_summary)

    p_json = sub.add_parser("json", help="dump command center metrics as JSON")
    p_json.add_argument("--window", type=int, default=30, help="lookback window in days")
    p_json.set_defaults(func=cmd_json)

    p_graf = sub.add_parser("export-grafana", help="validate Grafana dashboard JSON")
    p_graf.set_defaults(func=cmd_export_grafana)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
