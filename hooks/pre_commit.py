#!/usr/bin/env python3
"""PreCommit hook (BUILD-SPEC §7.2, class A <3s, local, blocking).

Runs on the staged diff only — the full suite belongs to pre_push/CI (G9).

Fails (exit != 0) when:
  - the staged diff contains a secret (I6; our scanner stands in for gitleaks,
    which is not guaranteed installed — the pattern table is lib/redact.py)
  - a staged path violates CODEOWNERS human ownership (§11.2)
  - a staged artifact fails fast schema validation (receipts, STATE, leases,
    envelopes — fast mode, stdlib only, inside the time budget)
  - a staged receipt breaks the hash chain (I15)
  - no task id is associated with the commit (MARZ_TASK_ID, commit message,
    or a staged receipt — every commit traces to a task)
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

import _common as H
from lib import receipts, redact, validate


def _git(*args: str) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=H.REPO_ROOT, capture_output=True,
                             text=True, timeout=5)
        return out.stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def main() -> None:
    H.read_stdin()

    staged = [l for l in _git("diff", "--cached", "--name-only").splitlines() if l.strip()]
    if not staged:
        H.allow()  # nothing staged: nothing to gate

    diff = _git("diff", "--cached", "-U0", "--no-color")
    if len(diff) > 500_000:
        diff = diff[:500_000]

    # 1. Secret scan over the staged diff (I6).
    scan = redact.scan_text(diff)
    if not scan.clean:
        kinds = ", ".join(sorted({f.kind for f in scan.findings}))
        H.block(f"secret in staged diff ({kinds}). Unstage, remove, rotate if it was "
                f"ever real (I6).", subject_kind="commit", subject_id="staged",
                payload={"findings": [f.kind for f in scan.findings]})

    # 2. CODEOWNERS human paths.
    if H.agent_id() != "owner":
        for rel in staged:
            for pattern in H.HUMAN_OWNED_GLOBS:
                if pattern.search(rel):
                    H.block(f"{rel} is human-owned (CODEOWNERS §11.2); agent commits "
                            f"here are proposals only.", subject_kind="file",
                            subject_id=rel)

    # 3. Fast schema validation of staged artifacts.
    problems: list[str] = []
    schema_for = {"state/STATE.json": "state", "state/KILL": None}
    for rel in staged:
        name = schema_for.get(rel, "state" if rel == "state/STATE.json" else None)
        if rel.startswith("receipts/") and rel.endswith(".json") and "/_chain/" not in rel:
            name = "receipt"
        elif rel.startswith("state/locks/") and rel.endswith(".lock.json"):
            name = "lease"
        elif rel.startswith("state/a2a/") and rel.endswith(".json"):
            name = "a2a-envelope"
        if not name:
            continue
        try:
            content = _git("show", f":{rel}")
            import json as _json
            obj = _json.loads(content)
            result = validate.validate(obj, name, strict=False)
            if not result.ok:
                problems.append(f"{rel}: " + "; ".join(result.errors[:2]))
        except Exception as exc:
            problems.append(f"{rel}: unreadable as {name}: {exc}")
    if problems:
        H.block("staged artifacts fail schema validation:\n  - " + "\n  - ".join(problems[:5]),
                subject_kind="commit", subject_id="staged")

    # 4. Chain integrity when receipts are staged (I15).
    if any(r.startswith("receipts/") for r in staged):
        report = receipts.verify_chain()
        if not report["ok"]:
            detail = "; ".join(p for ws in report["workstreams"].values()
                               for p in ws["problems"][:2])
            H.block(f"receipt chain is broken: {detail} (I15 — a chain break is a "
                    f"security incident, not a CI error)", subject_kind="receipt",
                    subject_id="chain")

    # 5. Task id traceability.
    msg = ""
    for candidate in (H.REPO_ROOT / ".git" / "COMMIT_EDITMSG",):
        if candidate.exists():
            msg = candidate.read_text(encoding="utf-8", errors="replace")
    has_task = (os.environ.get("MARZ_TASK_ID")
                or re.search(r"\bT-[A-Z0-9]{4,}\b", msg)
                or any(r.startswith("receipts/") for r in staged))
    if not has_task:
        H.block("no task id for this commit. Set MARZ_TASK_ID, reference T-… in the "
                "message, or stage the receipt. Every commit traces to a task (§7.2).",
                subject_kind="commit", subject_id="staged")

    H.emit("verify.passed", "commit", "staged", {"files": len(staged), "hook": "pre_commit"})
    H.allow()


if __name__ == "__main__":
    main()
