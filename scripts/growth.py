#!/usr/bin/env python3
"""growth.py — CLI for Growth Spine, Funnel Analytics, and NSM (BUILD-SPEC §13, VS-8)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(1, str(REPO / "scripts"))

from lib import growth, paths  # noqa: E402


def cmd_nsm(args: argparse.Namespace) -> int:
    res = growth.compute_nsm(window_days=args.days)
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"=== North Star Metric ({args.days}-Day Window) ===")
        print(f"NSM (Active Paid & Connected): {res['nsm_count']}")
        print(f"Paid Users: {res['paid_users_count']} | Connected Users: {res['connected_users_count']}")
        print(f"Traceable Events: {res['trace_events_count']} event IDs")
        if res["active_users"]:
            print(f"Active Users Sample: {res['active_users'][:10]}")
    return 0


def cmd_funnel(args: argparse.Namespace) -> int:
    res = growth.compute_funnel(window_days=args.days)
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        counts = res["counts"]
        rates = res["conversion_rates"]
        print(f"=== Conversion Funnel ({args.days}-Day Window) ===")
        print(f"1. Visits:   {counts['visit']}")
        print(f"2. Signups:  {counts['signup']} (visit->signup: {rates['visit_to_signup']*100:.1f}%)")
        print(f"3. Trials:   {counts['trial']} (signup->trial: {rates['signup_to_trial']*100:.1f}%)")
        print(f"4. Paid:     {counts['paid']} (trial->paid: {rates['trial_to_paid']*100:.1f}%)")
        print(f"5. Active:   {counts['active']} (paid->active: {rates['paid_to_active']*100:.1f}%)")
        print(f"Overall Visit->Paid: {rates['overall_visit_to_paid']*100:.2f}%")
    return 0


def cmd_economics(args: argparse.Namespace) -> int:
    res = growth.compute_unit_economics(
        arpu=args.arpu,
        infra_per_user=args.infra,
        payment_fee=args.payment_fee,
        support_cost=args.support,
        agent_token_cost_per_user=args.token_cost,
        cac=args.cac,
        expected_lifetime_months=args.months,
        target_cac=args.target_cac,
    )
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"=== Unit Economics Model ===")
        print(f"ARPU: ${res['arpu']:.2f} | Gross Profit / User: ${res['gross_profit_per_user']:.2f} ({res['gross_margin_pct']:.1f}%)")
        print(f"LTV: ${res['ltv']:.2f} | CAC: ${res['cac']:.2f}")
        print(f"LTV:CAC Ratio: {res['ltv_cac_ratio']:.2f}x (target > 3: {'PASS' if res['targets_met']['ltv_cac_gt_3'] else 'FAIL'})")
        print(f"CAC Payback: {res['cac_payback_months']:.1f} mo (target < 3mo: {'PASS' if res['targets_met']['payback_lt_3mo'] else 'FAIL'})")
        if res["stop_loss_triggered"]:
            print(f"WARNING: STOP-LOSS TRIGGERED! {res['stop_loss_reason']}")
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    payload = json.loads(args.payload) if args.payload else {}
    ev = growth.record_growth_event(
        args.type,
        args.user,
        payload=payload,
        campaign=args.campaign,
    )
    print(f"recorded event: {ev.type} (id: {ev.event_id}, user: {args.user})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="growth.py", description="Growth Spine & Funnel CLI")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # nsm
    p_nsm = subparsers.add_parser("nsm", help="compute North Star Metric")
    p_nsm.add_argument("--days", type=int, default=7, help="rolling window days (default: 7)")
    p_nsm.add_argument("--json", action="store_true")

    # funnel
    p_funnel = subparsers.add_parser("funnel", help="calculate customer conversion funnel")
    p_funnel.add_argument("--days", type=int, default=7, help="rolling window days (default: 7)")
    p_funnel.add_argument("--json", action="store_true")

    # economics
    p_econ = subparsers.add_parser("economics", help="calculate unit economics and stop-loss")
    p_econ.add_argument("--arpu", type=float, required=True, help="average revenue per user")
    p_econ.add_argument("--infra", type=float, default=2.0, help="infra cost per user")
    p_econ.add_argument("--payment-fee", type=float, default=0.5, help="payment fee per user")
    p_econ.add_argument("--support", type=float, default=1.0, help="support cost per user")
    p_econ.add_argument("--token-cost", type=float, default=0.5, help="agent token cost per user")
    p_econ.add_argument("--cac", type=float, required=True, help="customer acquisition cost")
    p_econ.add_argument("--months", type=int, default=12, help="expected lifetime months")
    p_econ.add_argument("--target-cac", type=float, help="target CAC for stop-loss calculation")
    p_econ.add_argument("--json", action="store_true")

    # record
    p_rec = subparsers.add_parser("record", help="record a growth or funnel event")
    p_rec.add_argument("--type", required=True, help="event type (e.g. funnel.visit, checkout.completed)")
    p_rec.add_argument("--user", required=True, help="anonymous user ID")
    p_rec.add_argument("--campaign", help="campaign tag")
    p_rec.add_argument("--payload", help="JSON payload")

    args = parser.parse_args(argv)
    handlers = {
        "nsm": cmd_nsm,
        "funnel": cmd_funnel,
        "economics": cmd_economics,
        "record": cmd_record,
    }
    return handlers[args.subcommand](args)


if __name__ == "__main__":
    sys.exit(main())
