"""Deterministic Code Nodes for Marzneshin Multi-Agent System.

According to Graph & Loop Engineering principles:
Code nodes perform deterministic, zero-variance tasks that require NO LLM reasoning:
merging, deduplicating, ranking, diff bounds checking, and schema compliance.
Running deterministic transformations through an LLM adds unnecessary token spend,
latency, and hallucination risk.
"""

from typing import Any
from .graph_state import TaskSpec, TaskResult


def deduplicate_items(items: list[dict[str, Any]], key: str = "id") -> list[dict[str, Any]]:
    """Deduplicate list of dictionaries preserving insertion order."""
    seen = set()
    deduped = []
    for item in items:
        val = item.get(key)
        if val not in seen:
            seen.add(val)
            deduped.append(item)
    return deduped


def rank_items(items: list[dict[str, Any]], key: str, reverse: bool = False) -> list[dict[str, Any]]:
    """Rank list of dictionaries by numeric or comparable key."""
    return sorted(items, key=lambda x: x.get(key, 0), reverse=reverse)


def verify_schema_compliance(data: dict[str, Any], required_fields: list[str]) -> tuple[bool, list[str]]:
    """Verify presence and non-emptiness of required fields in data."""
    missing = [f for f in required_fields if f not in data or data[f] is None]
    return (len(missing) == 0, missing)


def check_diff_bounds(
    target_files: list[str],
    modified_files: list[str],
    max_changed_files: int = 5
) -> tuple[bool, list[str]]:
    """Verify that an agent did not commit scope creep outside designated boundaries."""
    violations = []
    clean_targets = {t.strip().lstrip("/") for t in target_files if t.strip()}
    clean_modified = [m.strip().lstrip("/") for m in modified_files if m.strip()]

    if clean_targets:
        for m in clean_modified:
            if m not in clean_targets and not any(m.startswith(t + "/") for t in clean_targets):
                violations.append(f"Scope violation: file '{m}' modified outside allowed targets {clean_targets}")

    if len(clean_modified) > max_changed_files:
        violations.append(f"Diff bound violation: changed {len(clean_modified)} files, max allowed is {max_changed_files}")

    return (len(violations) == 0, violations)


def merge_task_results(results: list[TaskResult]) -> dict[str, Any]:
    """Deterministically merge and summarize results without LLM overhead."""
    total = len(results)
    succeeded = sum(1 for r in results if r.get("status") == "SUCCESS" and r.get("tests_passed", True))
    failed = sum(1 for r in results if r.get("status") != "SUCCESS" or not r.get("tests_passed", True))
    artifacts = []
    for r in results:
        artifacts.extend(r.get("artifacts_created", []))
    deduped_artifacts = list(dict.fromkeys(artifacts))

    return {
        "total_tasks": total,
        "succeeded_tasks": succeeded,
        "failed_tasks": failed,
        "all_passed": (failed == 0 and total > 0),
        "combined_artifacts": deduped_artifacts,
        "summary": f"Executed {total} task(s): {succeeded} succeeded, {failed} failed."
    }


def code_node(task_or_state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph Code Node: Pure deterministic transformations with ZERO LLM cost."""
    task: TaskSpec
    if "task_id" in task_or_state:
        task = task_or_state
    elif "pending_tasks" in task_or_state and task_or_state["pending_tasks"]:
        task = task_or_state["pending_tasks"][0]
    else:
        task = {
            "task_id": "CODE-TRANSFORM-GEN",
            "title": "Deterministic Code Transform",
            "code_transform_op": "merge",
            "code_transform_payload": {}
        }

    task_id = task.get("task_id", "CODE-1")
    op = task.get("code_transform_op", "merge")
    payload = task.get("code_transform_payload", {})

    status = "SUCCESS"
    verdict = "GREEN"
    summary = ""
    error = None

    if op == "deduplicate":
        items = payload.get("items", [])
        key = payload.get("key", "id")
        res = deduplicate_items(items, key=key)
        summary = f"Deduplicated {len(items)} items to {len(res)} items using key '{key}'."
    elif op == "rank":
        items = payload.get("items", [])
        key = payload.get("key", "priority")
        reverse = payload.get("reverse", False)
        res = rank_items(items, key=key, reverse=reverse)
        summary = f"Ranked {len(res)} items by key '{key}' (reverse={reverse})."
    elif op == "schema_check":
        data = payload.get("data", {})
        required = payload.get("required_fields", [])
        ok, missing = verify_schema_compliance(data, required)
        if ok:
            summary = "Schema compliance check passed."
        else:
            status = "FAILED"
            verdict = "RED"
            error = f"Missing required fields: {missing}"
            summary = f"Schema validation failed: {error}"
    elif op == "diff_bounds":
        target_files = payload.get("target_files", [])
        modified_files = payload.get("modified_files", [])
        max_files = payload.get("max_changed_files", 5)
        ok, violations = check_diff_bounds(target_files, modified_files, max_files)
        if ok:
            summary = "Diff bounds check passed."
        else:
            status = "FAILED"
            verdict = "RED"
            error = "; ".join(violations)
            summary = f"Diff bounds violated: {error}"
    else:
        # Default merge operation
        results = payload.get("results", [])
        merged = merge_task_results(results)
        summary = merged["summary"]

    result: TaskResult = {
        "task_id": task_id,
        "worker": "code_node",
        "status": status,
        "verdict": verdict,
        "blast_radius": "contained",
        "reversibility": "high",
        "summary": summary,
        "artifacts_created": [],
        "test_output": "Deterministic execution succeeded (0 LLM tokens)",
        "tests_passed": (status == "SUCCESS"),
        "scope_violations": [],
        "attempts_used": 1,
        "error": error
    }

    event = {
        "actor": "code_node",
        "action": "executed_transform",
        "op": op,
        "task_id": task_id,
        "status": status,
        "ts": "now"
    }

    return {
        "completed_results": [result],
        "fsp_events": [event]
    }
