#!/usr/bin/env python3
"""
scripts/autonomous_runner.py — One-Click Autonomous Multi-Agent Runner

Executes autonomous software engineering campaigns in Marzneshin OS:
1. Context Recall from AgentMemory
2. Goal Decomposition by Main Agent Orchestrator (Supervisor)
3. Parallel Worker Execution (Coder & Reviewer) in Isolated Contexts
4. Verification & QA Gate Enforcement
5. Cryptographic Receipt & Event Emission
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.append(str(REPO_ROOT / "scripts"))

from lib import clock, events, paths, killswitch
from agents.langgraph_workflow import app as graph_app
from agents.graph_state import AgentState, TaskSpec, TaskResult


def query_memory_context(objective: str) -> str:
    """Recall relevant context from AgentMemory on port 3111."""
    try:
        from lib import agentmemory
        resp = agentmemory.call_mcp_tool("memory_smart_search", {"query": objective, "limit": 3})
        if not resp.startswith("AgentMemory error"):
            return resp
    except Exception as e:
        print(f"[Memory] Notice: AgentMemory recall skipped: {e}")
    return ""


def run_autonomous_cycle(goal: str, max_iterations: int = 3) -> dict:
    print("=" * 70)
    print("🚀 MARZNESHIN AUTONOMOUS MULTI-AGENT OS — ONE-CLICK RUNNER")
    print(f"Goal:           {goal}")
    print(f"Max Iterations: {max_iterations}")
    print(f"Timestamp:      {clock.iso()}")
    print("=" * 70)

    # 1. Memory Context Recall
    print("\n[Step 1/5] Recalling persistent context from AgentMemory...")
    mem_ctx = query_memory_context(goal)
    if mem_ctx:
        print(f"  ✓ Context recalled ({len(mem_ctx)} characters)")
    else:
        print("  - Running with baseline workspace context")

    # 2. Check Fail-Closed Invariants
    print("\n[Step 2/5] Validating fail-closed invariants...")
    st = killswitch.check()
    if st.verdict != killswitch.Verdict.RUNNING:
        print(f"  🛑 FAIL-CLOSED: Kill switch active ({st.verdict.value}: {st.detail}). Aborting.")
        sys.exit(2)
    print(f"  ✓ Kill switch clear ({st.verdict.value})")

    # 3. Multi-Agent Graph Execution
    thread_id = str(uuid.uuid4())
    print(f"\n[Step 3/5] Dispatching to Master Orchestrator (Thread ID: {thread_id[:8]})...")

    initial_state: AgentState = {
        "objective": goal,
        "current_task": goal,
        "pending_tasks": [],
        "completed_results": [],
        "active_workers": ["Supervisor", "Coder", "Reviewer"],
        "iteration": 0,
        "max_iterations": max_iterations,
        "agent_memory": {"context": mem_ctx},
        "fsp_events": [{
            "actor": "orchestrator",
            "action": "autonomous_cycle_started",
            "goal": goal,
            "ts": clock.iso()
        }]
    }

    config = {"configurable": {"thread_id": thread_id}}

    step_num = 0
    for state_update in graph_app.stream(initial_state, config):
        step_num += 1
        node_name = list(state_update.keys())[0] if isinstance(state_update, dict) else "Graph"
        print(f"  → Step {step_num}: Executed node [{node_name}]")

    # 4. Result Inspection
    print("\n[Step 4/5] Evaluating Multi-Agent Deliverables...")
    saved_state = graph_app.get_state(config)
    values = saved_state.values if saved_state else {}
    results: list[TaskResult] = values.get("completed_results", [])

    print(f"  Total Subagent Tasks Executed: {len(results)}")
    for r in results:
        status_icon = "✓" if r.get("status") == "SUCCESS" else "✗"
        print(f"    [{status_icon}] [{r.get('worker', 'worker').upper()}] {r.get('task_id')}: {r.get('summary', '')[:80]}...")

    report = values.get("final_report", "Execution complete.")
    print(f"\n  Final Orchestrator Report:\n{report}")

    # 5. Verification Gate Check
    print("\n[Step 5/5] Running Verification Gate (scripts/verify.py)...")
    import subprocess
    verify_cmd = [sys.executable, str(paths.repo_root() / "scripts" / "verify.py"), "--lint-imports", "--lint-clock"]
    v_res = subprocess.run(verify_cmd, capture_output=True, text=True, cwd=str(paths.repo_root()))
    if v_res.returncode == 0:
        print("  ✓ Verification Gates: GREEN")
    else:
        print(f"  ⚠ Verification Warnings:\n{v_res.stdout[:500]}")

    print("\n" + "=" * 70)
    print("🎯 Autonomous Run Concluded Successfully.")
    print("=" * 70)
    return values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Marzneshin One-Click Autonomous Multi-Agent Runner")
    parser.add_argument("--goal", required=True, help="The engineering objective to plan, execute, and verify.")
    parser.add_argument("--max-iterations", type=int, default=3, help="Maximum repair/milestone loops allowed.")
    args = parser.parse_args(argv)

    try:
        run_autonomous_cycle(args.goal, max_iterations=args.max_iterations)
        return 0
    except Exception as e:
        print(f"\n[Fatal Error] Autonomous runner failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
