#!/usr/bin/env python3
"""TaskCompleted hook (BUILD-SPEC §7.2, I3).

A task is not Done without exactly one valid receipt. Fails (exit != 0) when:
  - no receipt exists for the task
  - the receipt fails its status contract (receipts._validate_for_status:
    verification evidence, tested rollback, sim_evidence for code changes...)
  - the receipt fails schema validation
  - the receipt is not in the chain (hash mismatch = tampered after write)

Task id resolution: MARZ_TASK_ID env, else stdin's task_id, else the newest
receipt for this session's agent is NOT assumed — absence of an id is a
failure, because guessing which task finished is how coverage leaks.
"""

from __future__ import annotations

import os

import _common as H
from lib import receipts, validate


def main() -> None:
    data = H.read_stdin()
    task_id = os.environ.get("MARZ_TASK_ID") or data.get("task_id")
    if not task_id:
        H.block("TaskCompleted with no task id (MARZ_TASK_ID unset). I3 cannot be "
                "checked against an unnamed task.", subject_kind="task",
                subject_id="unknown")

    body = receipts.read(task_id)
    if not body:
        H.block(f"no receipt for {task_id}. Write one via scripts/lib/receipts.py — "
                f"a task without a receipt does not exist (I3).",
                subject_kind="task", subject_id=task_id)

    # Status contract: re-run the same validation write() enforces.
    problems = []
    status = body.get("status")
    if status == "complete":
        if not any(v.get("result") == "pass" for v in body.get("verification", [])):
            problems.append("status=complete without a passing verification entry")
        rb = body.get("rollback") or {}
        if not rb.get("tested"):
            problems.append("rollback.tested != true (§19)")
        elif not rb.get("tested_at") or not rb.get("tested_in"):
            problems.append("rollback.tested=true without tested_at/tested_in (§3.3)")
        changes = body.get("changes", [])
        if any(receipts._is_code_or_config(c.get("path", "")) for c in changes) \
                and not body.get("sim_evidence"):
            problems.append("code/config change without sim_evidence (I11)")
    if status not in {"complete", "failed", "abandoned", "crashed", "superseded"}:
        problems.append(f"invalid status {status!r}")

    result = validate.validate(body, "receipt", strict=False)
    if not result.ok:
        problems.extend(result.errors[:3])

    # Chain membership: the stored hash must still match the content (I15).
    if receipts.content_hash(body) != body.get("receipt_hash"):
        problems.append("receipt_hash mismatch — the receipt was modified after writing")

    if problems:
        H.block(f"receipt {task_id} does not satisfy the DoD:\n  - "
                + "\n  - ".join(problems), subject_kind="task", subject_id=task_id,
                payload={"status": status})

    try:
        from lib import agentmemory, redact
        import json
        redacted_body = redact.redact_obj(body)
        agentmemory.call_mcp_tool("memory_save", {"content": f"Task {task_id} completed receipt: {json.dumps(redacted_body)}"})
    except Exception as e:
        H.emit("agentmemory.error", "sync", task_id, {"error": str(e)})

    H.emit("task.completed", "task", task_id,
           {"status": status, "hook": "task_complete"})
    H.allow()


if __name__ == "__main__":
    main()
