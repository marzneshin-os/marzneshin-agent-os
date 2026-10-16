#!/usr/bin/env python3
"""CLI utility for Marzneshin Graph & Loop Engineering Engine.

Usage:
  python3 scripts/graph_engine.py run --objective "Fix authentication redirect"
  python3 scripts/graph_engine.py gate --task-id "T-1" --blast-radius "contained" --tests-passed
  python3 scripts/graph_engine.py constraints
"""

import sys
import json
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.graph_loop import GraphLoopAdapter
from agents.gate_nodes import evaluate_unit_gate
from scripts.lib import clock


def cmd_run(args):
    adapter = GraphLoopAdapter(world="prod")
    deadline = clock.now() + clock.timedelta(minutes=5)
    res = adapter.execute(
        "run_pipeline",
        {"objective": args.objective, "max_iterations": args.max_iterations},
        idem_key=f"cli-run-{abs(hash(args.objective))}",
        idem_class="none",
        dry_run=args.dry_run,
        deadline=deadline,
        provenance=[{"field": "$.objective", "source": "cli", "trust": "internal"}]
    )
    if res.ok:
        print(json.dumps(res.data, indent=2))
        return 0
    else:
        print(f"Error: {res.error}", file=sys.stderr)
        return 1


def cmd_gate(args):
    task_res = {
        "task_id": args.task_id,
        "blast_radius": args.blast_radius,
        "tests_passed": args.tests_passed,
        "test_output": args.test_output,
        "scope_violations": args.scope_violations,
        "status": "SUCCESS" if args.tests_passed else "FAILED"
    }
    verdict = evaluate_unit_gate(task_res, allow_irreversible=args.allow_irreversible)
    print(json.dumps(verdict, indent=2))
    return 0 if verdict["verdict"] == "GREEN" else 1


def cmd_constraints(args):
    adapter = GraphLoopAdapter(world="prod")
    deadline = clock.now() + clock.timedelta(seconds=10)
    res = adapter.execute(
        "get_learned_constraints",
        {},
        idem_key="cli-constraints",
        idem_class="none",
        dry_run=False,
        deadline=deadline,
        provenance=[]
    )
    print(json.dumps(res.data, indent=2))
    return 0


def main():
    parser = argparse.ArgumentParser(description="Marzneshin Graph & Loop Engine CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # run command
    p_run = sub.add_parser("run", help="Run multi-agent graph pipeline")
    p_run.add_argument("--objective", "-o", required=True, help="Objective to execute")
    p_run.add_argument("--max-iterations", type=int, default=3, help="Max loop iterations")
    p_run.add_argument("--dry-run", action="store_true", help="Validate without mutation")

    # gate command
    p_gate = sub.add_parser("gate", help="Evaluate a unit against blast radius gate")
    p_gate.add_argument("--task-id", required=True, help="Task ID")
    p_gate.add_argument("--blast-radius", choices=["contained", "wide", "irreversible"], default="contained")
    p_gate.add_argument("--tests-passed", action="store_true", help="Flag if tests passed")
    p_gate.add_argument("--test-output", default="", help="Test output snippet")
    p_gate.add_argument("--scope-violations", nargs="*", default=[], help="Scope violation files")
    p_gate.add_argument("--allow-irreversible", action="store_true", help="Allow irreversible action")

    # constraints command
    p_const = sub.add_parser("constraints", help="List learned constraints")

    args = parser.parse_args()
    if args.cmd == "run":
        return cmd_run(args)
    elif args.cmd == "gate":
        return cmd_gate(args)
    elif args.cmd == "constraints":
        return cmd_constraints(args)


if __name__ == "__main__":
    sys.exit(main())
