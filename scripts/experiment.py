#!/usr/bin/env python3
"""experiment.py — CLI for Safe Experimentation, SRM, Guardrails, and Readouts (BUILD-SPEC §13.4, VS-9)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(1, str(REPO / "scripts"))

from lib import experiments  # noqa: E402


def cmd_create(args: argparse.Namespace) -> int:
    guardrails = {}
    if args.guardrail:
        for item in args.guardrail:
            k, v = item.split("=", 1)
            guardrails[k.strip()] = float(v.strip())

    res = experiments.create_experiment(
        args.name,
        args.hypothesis,
        variant_a=args.variant_a,
        variant_b=args.variant_b,
        primary_metric=args.metric,
        guardrail_metrics=guardrails or None,
        mde=args.mde,
        target_ratio=args.target_ratio,
    )
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"experiment created: {res['experiment_id']} (name: {res['name']}, n_min: {res['n_min']})")
    return 0


def cmd_readout(args: argparse.Namespace) -> int:
    guardrails = {}
    if args.guardrail:
        for item in args.guardrail:
            k, v = item.split("=", 1)
            guardrails[k.strip()] = float(v.strip())

    res = experiments.evaluate_readout(
        args.id,
        samples_a=args.samples_a,
        ok_a=args.ok_a,
        samples_b=args.samples_b,
        ok_b=args.ok_b,
        guardrail_values=guardrails,
        final_readout=args.final,
    )
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"=== Experiment Readout: {args.id} ===")
        print(f"Verdict: {res['verdict'].upper()}")
        print(f"Reason: {res['reason']}")
        if "readout" in res:
            r = res["readout"]
            print(f"Rates: control={r['rate_a']:.4f} vs treatment={r['rate_b']:.4f} (delta={r['delta']:+.4f}, p_val={r['p_value']:.4f})")
            print(f"SRM: {'DETECTED (BIASED)' if r['srm']['srm_detected'] else 'CLEAN'} (chi2={r['srm']['chi_square']}, p={r['srm']['p_value']})")
    return 0 if res["verdict"] in ("ship", "inconclusive") else 1


def cmd_decision(args: argparse.Namespace) -> int:
    res = experiments.record_decision(
        args.id,
        decision=args.decision,
        reason=args.reason,
        evidence={"manual_override": True},
        is_negative_result=(args.decision == "kill"),
    )
    print(f"experiment {args.id}: decision recorded as {res['verdict']} (reason: {args.reason})")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    exps = experiments.list_experiments()
    if args.json:
        print(json.dumps(exps, indent=2))
    else:
        print(f"=== Active & Completed Experiments ({len(exps)}) ===")
        for e in exps:
            dec = f" -> DECISION: {e['decision']['decision'].upper()}" if e.get("decision") else ""
            print(f"- {e['experiment_id']}: name={e['name']}, status={e['status']}, n_min={e['n_min']}{dec}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="experiment.py", description="Safe Experimentation & Readout CLI")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # create
    p_create = subparsers.add_parser("create", help="create a new experiment")
    p_create.add_argument("--name", required=True, help="experiment name")
    p_create.add_argument("--hypothesis", required=True, help="hypothesis statement")
    p_create.add_argument("--variant-a", default="control")
    p_create.add_argument("--variant-b", default="treatment")
    p_create.add_argument("--metric", default="conversion_rate")
    p_create.add_argument("--mde", type=float, default=0.02)
    p_create.add_argument("--target-ratio", type=float, default=0.5)
    p_create.add_argument("--guardrail", action="append", help="guardrail metric bound in format name=value")
    p_create.add_argument("--json", action="store_true")

    # readout
    p_readout = subparsers.add_parser("readout", help="evaluate experiment readout")
    p_readout.add_argument("--id", required=True, help="experiment ID")
    p_readout.add_argument("--samples-a", type=int, required=True)
    p_readout.add_argument("--ok-a", type=int, required=True)
    p_readout.add_argument("--samples-b", type=int, required=True)
    p_readout.add_argument("--ok-b", type=int, required=True)
    p_readout.add_argument("--guardrail", action="append", help="observed guardrail value in format name=value")
    p_readout.add_argument("--final", action="store_true", help="flag as final readout at end of trial")
    p_readout.add_argument("--json", action="store_true")

    # decision
    p_dec = subparsers.add_parser("decision", help="record ship or kill decision manually")
    p_dec.add_argument("--id", required=True)
    p_dec.add_argument("--decision", choices=["ship", "kill"], required=True)
    p_dec.add_argument("--reason", required=True)

    # status
    p_status = subparsers.add_parser("status", help="list all experiments")
    p_status.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    handlers = {
        "create": cmd_create,
        "readout": cmd_readout,
        "decision": cmd_decision,
        "status": cmd_status,
    }
    return handlers[args.subcommand](args)


if __name__ == "__main__":
    sys.exit(main())
