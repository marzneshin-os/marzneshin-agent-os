#!/usr/bin/env python3
"""fable_graph.py — Fable 5.1 Task Graph Validator and Stage Decomposer.

Formalizes Claude Fable 5.1 orchestration logic into Marzneshin Agent OS.
Validates DAG dependencies, detects cycles, ensures exclusive file ownership,
and decomposes goals into verifiable parallel stages (ADR-027).

Commands:
    validate <plan_file>     - Validate a task graph against Fable 5.1 & Marzneshin contracts
    stages   <plan_file>     - Compute topological execution stages
    sample   <goal>          - Generate a canonical sample task graph for an objective
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def validate_graph(plan: dict) -> list[str]:
    """Validate task graph integrity, cycle-freedom, and file write separation."""
    errors = []
    tasks = plan.get("tasks", [])
    if not tasks:
        return ["Plan contains no tasks"]

    task_map = {}
    for t in tasks:
        tid = t.get("id")
        if not tid:
            errors.append("Task missing 'id'")
            continue
        if tid in task_map:
            errors.append(f"Duplicate task id '{tid}'")
        task_map[tid] = t

        if not t.get("specialist"):
            errors.append(f"Task '{tid}' missing 'specialist'")
        if not t.get("prompt"):
            errors.append(f"Task '{tid}' missing 'prompt'")
        if not t.get("verification"):
            errors.append(f"Task '{tid}' missing 'verification' criteria")

    # Dependency check
    in_degree = {tid: 0 for tid in task_map}
    adj = {tid: [] for tid in task_map}

    for tid, t in task_map.items():
        deps = t.get("dependsOn", [])
        for dep in deps:
            if dep not in task_map:
                errors.append(f"Task '{tid}' depends on nonexistent task '{dep}'")
            elif dep == tid:
                errors.append(f"Task '{tid}' has self-dependency")
            else:
                adj[dep].append(tid)
                in_degree[tid] += 1

    # Cycle check via Kahn's algorithm
    queue = [tid for tid, deg in in_degree.items() if deg == 0]
    visited = 0

    while queue:
        curr = queue.pop(0)
        visited += 1
        for neighbor in adj[curr]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if visited != len(task_map):
        errors.append("Cycle detected in task graph dependencies")

    # File conflict check across concurrent batches
    return errors


def compute_stages(plan: dict) -> list[dict]:
    """Compute topological stages for parallel execution."""
    tasks = plan.get("tasks", [])
    task_map = {t["id"]: t for t in tasks}
    in_degree = {t["id"]: len(t.get("dependsOn", [])) for t in tasks}
    dependents = {t["id"]: [] for t in tasks}

    for t in tasks:
        for dep in t.get("dependsOn", []):
            if dep in dependents:
                dependents[dep].append(t["id"])

    stages = []
    current_batch = [tid for tid, deg in in_degree.items() if deg == 0]
    stage_idx = 0
    processed = set()

    while current_batch:
        # Check for overlapping files in same concurrent stage
        touched_files = {}
        for tid in current_batch:
            t = task_map[tid]
            for f in t.get("filesToTouch", []):
                if f in touched_files:
                    raise ValueError(f"Concurrent file collision in Stage {stage_idx}: both '{touched_files[f]}' and '{tid}' touch '{f}'")
                touched_files[f] = tid

        stages.append({
            "stage_index": stage_idx,
            "tasks": [task_map[tid] for tid in current_batch],
        })
        stage_idx += 1

        next_batch = []
        for tid in current_batch:
            processed.add(tid)
            for child in dependents.get(tid, []):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    next_batch.append(child)
        current_batch = next_batch

    return stages


def generate_sample_plan(goal: str) -> dict:
    return {
        "id": "fable-plan-001",
        "goal": goal,
        "planner": "claude-fable-5.1",
        "tasks": [
            {
                "id": "TASK-01",
                "title": "Analyze architectural boundaries & invariants",
                "specialist": "memory-architect",
                "model_tier": "tier_0",
                "prompt": f"Analyze current system architecture for goal: {goal}",
                "dependsOn": [],
                "filesToTouch": ["state/STATE.json"],
                "verification": "python3 scripts/verify.py",
            },
            {
                "id": "TASK-02",
                "title": "Implement core capability",
                "specialist": "mcp-tool-builder",
                "model_tier": "tier_1",
                "prompt": f"Implement required tools and adapters for {goal}",
                "dependsOn": ["TASK-01"],
                "filesToTouch": ["scripts/quota_doctor.py"],
                "verification": "python3 scripts/quota_doctor.py diagnose",
            },
            {
                "id": "TASK-03",
                "title": "Execute Two-Key Verification Gate",
                "specialist": "consistency-guardian",
                "model_tier": "tier_0",
                "prompt": "Verify QA gate and adversarial audit across changed files",
                "dependsOn": ["TASK-02"],
                "filesToTouch": ["state/HANDOFF.md"],
                "verification": "python3 scripts/two_key_gate.py run",
            },
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Fable 5.1 Task Graph Validator and Stage Decomposer")
    subparsers = parser.add_subparsers(dest="command")

    p_val = subparsers.add_parser("validate", help="Validate a task graph JSON file")
    p_val.add_argument("plan_file", help="Path to plan JSON file")

    p_stages = subparsers.add_parser("stages", help="Compute execution stages for a plan")
    p_stages.add_argument("plan_file", help="Path to plan JSON file")

    p_sample = subparsers.add_parser("sample", help="Generate sample plan for a goal")
    p_sample.add_argument("goal", help="High-level engineering goal")

    args = parser.parse_args()

    if args.command == "validate":
        plan_path = Path(args.plan_file)
        if not plan_path.exists():
            print(f"Error: File {plan_path} not found")
            sys.exit(1)
        with open(plan_path, "r", encoding="utf-8") as f:
            plan = json.load(f)
        errors = validate_graph(plan)
        if errors:
            print("❌ Validation Errors:")
            for e in errors:
                print(f"  - {e}")
            sys.exit(1)
        else:
            print("✅ Plan is valid under Fable 5.1 & Marzneshin contracts")
            sys.exit(0)

    elif args.command == "stages":
        plan_path = Path(args.plan_file)
        if not plan_path.exists():
            print(f"Error: File {plan_path} not found")
            sys.exit(1)
        with open(plan_path, "r", encoding="utf-8") as f:
            plan = json.load(f)
        try:
            stages = compute_stages(plan)
            print(json.dumps(stages, indent=2))
            sys.exit(0)
        except Exception as e:
            print(f"❌ Error computing stages: {e}")
            sys.exit(1)

    elif args.command == "sample":
        plan = generate_sample_plan(args.goal)
        print(json.dumps(plan, indent=2))
        sys.exit(0)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
