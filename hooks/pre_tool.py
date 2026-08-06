#!/usr/bin/env python3
"""PreToolUse hook (BUILD-SPEC §7.2, class A <3s).

Blocks (exit 2) when:
  - a secret appears in the tool arguments (I6 — before the tool runs, not after)
  - Edit/Write targets an append-only or derived store that must only be
    written by scripts (receipts/, state/events/, state/locks/, state/budget/,
    state/a2a/, state/KILL, state/STATE.json) — hand edits break the chain
    and the fencing model (I15, §3.6)
  - the kill switch does not allow a mutating operation at the requested
    autonomy (fail-closed; §6.3)
  - a write lands on a human-owned CODEOWNERS path while the actor is not
    the Owner (§11.2: four paths, everything else has an agent gate)
  - a write lands inside a workstream leased to SOMEONE ELSE (§3.6 fencing)
  - Bash carries an obviously destructive payload (rm -rf /, fork bomb, mkfs…)

High-frequency hook, so event emission is deny-only (ADR-003 D19): allows are
auditable via the tool log itself; denies are the decisions that must never be
lost.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import _common as H
from lib import killswitch, leases, redact

MUTATING_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}

# Stores whose writers are scripts, never hands. The chain, the partitions and
# the fencing model only hold if every write goes through lib/.
SCRIPT_ONLY_PREFIXES = (
    "receipts/", "state/events/", "state/locks/", "state/budget/", "state/a2a/",
)
SCRIPT_ONLY_FILES = {
    "state/KILL": "use scripts/killswitch.py engage/release",
    "state/STATE.json": "STATE.json is derived — use scripts/compact.py",
    "state/KILL.heartbeat.json": "written by the heartbeat workflow / killswitch.py",
}

# Human-owned paths: defined once in _common (H.HUMAN_OWNED_GLOBS).

_DESTRUCTIVE = (
    re.compile(r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\s+(/|/\*|~|\$HOME)(?=\s|$)"),
    re.compile(r":\(\)\s*\{\s*:\|:&\s*\}\s*;:"),          # fork bomb
    re.compile(r"\bmkfs\b"), re.compile(r"\bdd\s+.*of=/dev/"),
    re.compile(r"\bgit\s+push\b.*\b--force\b.*\b(main|master)\b"),
)


def _repo_rel(path_str: str) -> str | None:
    try:
        p = Path(path_str).resolve()
        return p.relative_to(H.REPO_ROOT).as_posix()
    except (ValueError, OSError):
        return None


def _check_write(path_str: str) -> None:
    rel = _repo_rel(path_str)
    if rel is None:
        return  # outside the repo: not ours to police

    if rel in SCRIPT_ONLY_FILES:
        H.block(f"{rel} must not be hand-edited — {SCRIPT_ONLY_FILES[rel]}",
                subject_kind="file", subject_id=rel)
    for prefix in SCRIPT_ONLY_PREFIXES:
        if rel.startswith(prefix):
            H.block(f"{rel} is inside an append-only/script-owned store ({prefix}). "
                    f"Writes there go through scripts (fsp/reaper/killswitch/lib), "
                    f"never through an editor — hand edits break the receipt chain "
                    f"and the fencing model (I15, §3.6).",
                    subject_kind="file", subject_id=rel)

    for pattern in H.HUMAN_OWNED_GLOBS:
        if pattern.search(rel) and H.agent_id() != "owner":
            H.block(f"{rel} is in a human-owned path (CODEOWNERS §11.2). Agents may "
                    f"only produce proposals for these four paths.",
                    subject_kind="file", subject_id=rel)

    # Fencing: a write inside a workstream leased to someone else is the
    # split-brain the token exists to prevent (§3.6).
    for lease in leases.list_all():
        if lease.holder == f"agent:{H.agent_id()}" or lease.expired():
            continue
        token = os.environ.get("MARZ_FENCING_TOKEN")
        if token is not None and int(token) >= lease.fencing_token:
            continue
        # Only state-plane writes are fenced; code files are gated by owns.
        if rel.startswith("state/"):
            H.block(f"{rel} falls under workstream {lease.workstream!r} leased to "
                    f"{lease.holder} (fencing token {lease.fencing_token}). Acquire the "
                    f"lease (scripts/fsp.py claim) before writing state.",
                    subject_kind="file", subject_id=rel)


def main() -> None:
    data = H.read_stdin()
    tool = data.get("tool_name", "")
    args = data.get("tool_input", {}) or {}

    # I6 — secrets never enter a tool call, because tool calls get logged.
    scan = redact.scan_text(json.dumps(args, ensure_ascii=False))
    if not scan.clean:
        kinds = ", ".join(sorted({f.kind for f in scan.findings}))
        H.block(f"secret detected in tool arguments ({kinds}). Remove it; use the "
                f"vault adapter for credentials (I6).",
                event_type="policy.denied", subject_kind="tool", subject_id=tool,
                payload={"findings": [f.kind for f in scan.findings]})

    if tool in MUTATING_TOOLS:
        ks = killswitch.check(agent=H.agent_id(), autonomy_level=2)
        if not ks.allows(2):
            verdict = "engaged" if ks.killed else "unknown (fail-closed)"
            H.block(f"kill switch {verdict}: mutating tools are halted. {ks.detail}",
                    event_type="killswitch.unknown", subject_kind="killswitch",
                    subject_id="global")
        _check_write(str(args.get("file_path", "")))

    if tool == "Bash":
        command = str(args.get("command", ""))
        for pattern in _DESTRUCTIVE:
            if pattern.search(command):
                H.block(f"destructive command pattern: {command[:120]!r}. If this is "
                        f"truly intended, the Owner runs it by hand.",
                        subject_kind="tool", subject_id="Bash")

    H.allow()


if __name__ == "__main__":
    main()
