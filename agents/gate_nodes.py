"""Blast-Radius Driven Gate Nodes & Dual Return Paths for Marzneshin.

According to Graph & Loop Engineering principles:
1. Gates do NOT open on model 'confidence scores' (which models easily hallucinate).
2. Gates open on BLAST RADIUS and REVERSIBILITY:
   - Lane 1: Contained & Reversible -> Opens on deterministic tests pass + diff bounds.
   - Lane 2: Wide & Reversible -> Opens on deterministic checks + clean trajectory.
   - Lane 3: Irreversible & Critical -> Autonomous gate is CLOSED; requires human or Two-Key approval.
3. Dual Return Paths:
   - Correction Edge (Short): Return the UNIT, NOT the batch!
     Carries: Unit ID, Verdict (RED), Reason, Evidence (line/error), Scope constraint.
     Capped at max attempts (e.g. 3).
   - Learning Edge (Long): Derives a permanent constraint from accepted results and feeds it
     back into the Splitter's brief for all subsequent runs.
"""

from typing import Any
from .graph_state import AgentState, TaskSpec, TaskResult, BlastRadius, GateVerdict


def evaluate_unit_gate(
    result: TaskResult,
    task_spec: TaskSpec | None = None,
    allow_irreversible: bool = False
) -> dict[str, Any]:
    """Evaluate an individual TaskResult against the Blast-Radius Gating Policy."""
    blast_radius: BlastRadius = result.get("blast_radius") or (task_spec.get("blast_radius") if task_spec else "contained") or "contained"
    reversibility = result.get("reversibility") or (task_spec.get("reversibility") if task_spec else "high") or "high"
    tests_passed = result.get("tests_passed", False)
    scope_violations = result.get("scope_violations", [])
    status = result.get("status", "SUCCESS")
    task_id = result.get("task_id", "T-UNKNOWN")
    error = result.get("error") or ""

    verdict: GateVerdict = "GREEN"
    reason = "Passed deterministic gate checks."
    evidence = result.get("test_output", "")[:400]
    derived_constraint = result.get("derived_constraint", "")

    # Check 1: Scope creep violation (Deterministic Check)
    if scope_violations:
        verdict = "RED"
        reason = f"Scope violation detected: {'; '.join(scope_violations)}"
        evidence = reason
    # Check 2: Deterministic test execution failed
    elif not tests_passed or status != "SUCCESS":
        verdict = "RED"
        reason = f"Verification failure: {error or 'Tests did not exit 0'}"
        evidence = result.get("test_output", error)[:400]
    # Check 3: Lane 3 Blast Radius (Irreversible / Critical)
    elif blast_radius == "irreversible":
        if not allow_irreversible:
            verdict = "BLOCKED"
            reason = "Lane 3 Blast Radius: Irreversible action requires Two-Key / human authorization."
            evidence = "Autonomous gate closed by policy (§4 fail-closed)."
        else:
            verdict = "GREEN"
            reason = "Irreversible action approved via explicit authorization key."

    # Generate Learning Edge constraint on GREEN if not explicitly present
    if verdict == "GREEN" and not derived_constraint:
        summary_clean = result.get("summary", "").replace("\n", " ").strip()
        derived_constraint = f"Unit [{task_id}] verified green: {summary_clean[:120]}"

    return {
        "task_id": task_id,
        "verdict": verdict,
        "blast_radius": blast_radius,
        "reversibility": reversibility,
        "reason": reason,
        "evidence": evidence,
        "derived_constraint": derived_constraint if verdict == "GREEN" else ""
    }


def gate_node(state: AgentState) -> dict[str, Any]:
    """LangGraph Gate Node: Evaluates all completed results, routes returns, and stores learnings."""
    completed = state.get("completed_results", [])
    pending = {t.get("task_id"): t for t in state.get("pending_tasks", [])}
    iteration = state.get("iteration", 1)
    max_iterations = state.get("max_iterations", 3)

    gate_verdicts: list[dict[str, Any]] = []
    rejected_units: list[TaskSpec] = []
    new_learned_constraints: list[str] = []
    blast_radius_summary = {"contained": 0, "wide": 0, "irreversible": 0}

    for res in completed:
        t_id = res.get("task_id", "")
        t_spec = pending.get(t_id)
        eval_res = evaluate_unit_gate(res, t_spec)
        gate_verdicts.append(eval_res)

        br = eval_res["blast_radius"]
        if br in blast_radius_summary:
            blast_radius_summary[br] += 1

        if eval_res["verdict"] == "RED":
            # SHORT RETURN PATH: Return the UNIT, NOT the batch!
            attempts = (t_spec.get("attempts", 1) if t_spec else 1) + 1
            max_attempts = (t_spec.get("max_attempts", 3) if t_spec else 3)

            if attempts <= max_attempts:
                # Construct focused correction unit
                target_f = t_spec.get("target_files", []) if t_spec else res.get("artifacts_created", [])
                scope = t_spec.get("scope_constraint") if t_spec else (target_f[0] if target_f else "")
                desc_lines = [
                    f"UNIT: {t_id}",
                    "VERDICT: RED",
                    f"REASON: {eval_res['reason']}",
                    f"EVIDENCE: {eval_res['evidence']}",
                    f"SCOPE: Fix this file/unit only ({scope}), do not touch other slices."
                ]
                correction_task: TaskSpec = {
                    "task_id": f"{t_id}-fix",
                    "assigned_to": t_spec.get("assigned_to", "Coder") if t_spec else "Coder",
                    "title": f"Correct unit: {t_id}",
                    "description": "\n".join(desc_lines),
                    "target_files": target_f,
                    "scope_constraint": scope,
                    "memory_context": t_spec.get("memory_context", "") if t_spec else "",
                    "blast_radius": br,
                    "reversibility": eval_res["reversibility"],
                    "attempts": attempts,
                    "max_attempts": max_attempts,
                    "verdict_evidence": eval_res["evidence"],
                    "iteration": iteration + 1
                }
                rejected_units.append(correction_task)
        elif eval_res["verdict"] == "GREEN":
            # LONG RETURN PATH: Learning Edge constraint
            derived = eval_res.get("derived_constraint")
            if derived:
                new_learned_constraints.append(derived)

    # Determine next routing
    has_rejected = len(rejected_units) > 0

    if has_rejected and iteration < max_iterations:
        next_agent = "parallel_dispatch"
    else:
        next_agent = "Supervisor"

    event = {
        "actor": "gate",
        "action": "evaluated_gate",
        "total": len(gate_verdicts),
        "green": sum(1 for v in gate_verdicts if v["verdict"] == "GREEN"),
        "red": sum(1 for v in gate_verdicts if v["verdict"] == "RED"),
        "blocked": sum(1 for v in gate_verdicts if v["verdict"] == "BLOCKED"),
        "rejected_count": len(rejected_units),
        "ts": "now"
    }

    return {
        "gate_verdicts": gate_verdicts,
        "rejected_units": rejected_units,
        "pending_tasks": rejected_units if has_rejected else [],
        "learned_constraints": new_learned_constraints,
        "blast_radius_summary": blast_radius_summary,
        "next_agent": next_agent,
        "fsp_events": [event]
    }
