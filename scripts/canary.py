#!/usr/bin/env python3
"""canary.py — CLI for Canary Deployments, Statistical Gates, and Auto-Rollback (BUILD-SPEC §5.7, VS-7)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(1, str(REPO / "scripts"))

from lib import canary, paths, probe_fleet  # noqa: E402


def cmd_deploy(args: argparse.Namespace) -> int:
    res = canary.deploy_canary(
        args.profile,
        initial_pct=args.initial_pct,
        mde=args.mde,
    )
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"canary deployed: {res['experiment_id']} (profile: {res['profile']}, stage: {res['current_stage_pct']}%, n_min: {res['n_min']})")
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    exp = canary.get_canary(args.experiment_id)
    if not exp:
        print(f"error: experiment {args.experiment_id} not found", file=sys.stderr)
        return 1

    pf = probe_fleet.get_latest_probe_result() or probe_fleet.sample_fleet()
    samples = args.samples if args.samples is not None else pf.total_samples
    ok = args.ok if args.ok is not None else pf.total_ok

    decision = canary.evaluate_canary_gate(
        current_stage_pct=exp["current_stage_pct"],
        samples=samples,
        ok=ok,
        probe_fleet_result=pf,
        error_budget_exhausted=args.error_budget_exhausted,
        mde=exp.get("mde", canary.DEFAULT_MDE),
    )

    if args.json:
        print(json.dumps(decision.to_dict(), indent=2))
    else:
        print(f"verdict: {decision.verdict.upper()} | stage: {decision.current_stage_pct}% -> {decision.next_stage_pct}% | csr: {decision.csr:.4f} | p_val: {decision.p_value:.4f}")
        print(f"reason: {decision.reason}")
    return 0 if decision.verdict in ("promote", "hold") else 1


def cmd_promote(args: argparse.Namespace) -> int:
    pf = probe_fleet.get_latest_probe_result() or probe_fleet.sample_fleet()
    res = canary.promote_canary(
        args.experiment_id,
        samples=args.samples,
        ok=args.ok,
        probe_fleet_result=pf,
        error_budget_exhausted=args.error_budget_exhausted,
    )
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        if res.get("ok"):
            print(f"canary: PROMOTED to {res.get('stage')}% (verdict: {res.get('verdict')})")
        else:
            print(f"canary: NOT PROMOTED (verdict: {res.get('verdict')}, stage remains {res.get('stage')}%)")
            print(f"reason: {res.get('decision', {}).get('reason')}")
    return 0 if res.get("ok") else 1


def cmd_rollback(args: argparse.Namespace) -> int:
    res = canary.rollback_canary(
        args.experiment_id,
        reason=args.reason,
    )
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"canary: ROLLED BACK {args.experiment_id} -> restored baseline {res.get('restored_profile')}")
        print(f"reason: {args.reason}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    canaries = canary.list_canaries()
    pf = probe_fleet.get_latest_probe_result()
    report = {
        "active_canaries": canaries,
        "probe_fleet": pf.to_dict() if pf else None,
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"=== Active Canary Experiments ({len(canaries)}) ===")
        for c in canaries:
            rb_info = f" [ROLLED BACK: {c.get('rollback', {}).get('reason')}]" if c.get("status") == "rolled_back" else ""
            print(f"- {c['experiment_id']}: profile={c['profile']}, stage={c['current_stage_pct']}%, status={c['status']}{rb_info}")
        if pf:
            print(f"\nProbe Fleet: {'HEALTHY' if pf.healthy else 'DEGRADED'} | CSR={pf.csr:.4f} | ASNs={pf.healthy_asns}")
        else:
            print("\nProbe Fleet: No samples recorded yet.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="canary.py", description="Canary Pipeline & Auto-Rollback CLI")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # deploy
    p_deploy = subparsers.add_parser("deploy", help="deploy a new canary profile")
    p_deploy.add_argument("--profile", required=True, help="configuration profile name")
    p_deploy.add_argument("--initial-pct", type=int, default=1, help="initial canary traffic percentage (default: 1)")
    p_deploy.add_argument("--mde", type=float, default=canary.DEFAULT_MDE, help="minimum detectable effect")
    p_deploy.add_argument("--json", action="store_true")

    # evaluate
    p_eval = subparsers.add_parser("evaluate", help="evaluate canary promotion gate")
    p_eval.add_argument("--experiment-id", required=True)
    p_eval.add_argument("--samples", type=int, help="override sample count")
    p_eval.add_argument("--ok", type=int, help="override successful sample count")
    p_eval.add_argument("--error-budget-exhausted", action="store_true", help="simulate exhausted error budget")
    p_eval.add_argument("--json", action="store_true")

    # promote
    p_promote = subparsers.add_parser("promote", help="promote canary to next stage")
    p_promote.add_argument("--experiment-id", required=True)
    p_promote.add_argument("--samples", type=int, help="override sample count")
    p_promote.add_argument("--ok", type=int, help="override successful sample count")
    p_promote.add_argument("--error-budget-exhausted", action="store_true", help="simulate exhausted error budget")
    p_promote.add_argument("--json", action="store_true")

    # rollback
    p_rb = subparsers.add_parser("rollback", help="roll back canary to baseline")
    p_rb.add_argument("--experiment-id", required=True)
    p_rb.add_argument("--reason", required=True, help="rollback justification")
    p_rb.add_argument("--json", action="store_true")

    # status
    p_status = subparsers.add_parser("status", help="show canary and probe fleet status")
    p_status.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    handlers = {
        "deploy": cmd_deploy,
        "evaluate": cmd_evaluate,
        "promote": cmd_promote,
        "rollback": cmd_rollback,
        "status": cmd_status,
    }
    return handlers[args.subcommand](args)


if __name__ == "__main__":
    sys.exit(main())
