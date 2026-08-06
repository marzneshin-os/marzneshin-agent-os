#!/usr/bin/env python3
"""Shared hook plumbing (BUILD-SPEC §7.2).

Hooks are thin layers over scripts/lib: the only logic allowed here is stdin/
stdout plumbing and identity resolution. Everything checkable lives in lib.

Protocol (Claude Code):
  - input:  one JSON object on stdin
  - allow:  exit 0 (optionally JSON on stdout)
  - block:  exit 2 — stdout JSON carries {"hookSpecificOutput":
            {"permissionDecision": "deny", ...}} or {"decision": "block"}
  - every hook outputs JSON and records its own event (§7.2)
  - no hook performs network I/O, ever (G9)
  - a hook never answers "suspicious but allow": ambiguity exits non-zero

Time budget: class A hooks run in <3s. Event emission is a local O_APPEND
write; it stays. What does NOT stay is anything that can block on I/O.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from typing import Any, NoReturn

HOOKS_DIR = Path(__file__).resolve().parent
REPO_ROOT = HOOKS_DIR.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

# Every lib call in every hook resolves against the repo that owns the hook,
# regardless of the caller's cwd.
os.environ.setdefault("MARZNESHIN_OPS_ROOT", str(REPO_ROOT))

from lib import clock, events  # noqa: E402

# Human-owned paths (CODEOWNERS, §11.2): configs/pricing/**, **/ToS*,
# infra/terraform/**, security/iam/**. An agent may propose but never land.
# Shared by pre_tool and pre_commit so the boundary is defined exactly once.
import re as _re

HUMAN_OWNED_GLOBS = (
    _re.compile(r"^configs/pricing/"),
    _re.compile(r"(^|/)ToS[^/]*$"),
    _re.compile(r"^infra/terraform/"),
    _re.compile(r"^security/iam/"),
)


def read_stdin() -> dict:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, OSError):
        return {}


def agent_id() -> str:
    return os.environ.get("MARZ_AGENT_ID", "owner")


def session_id(default: str = "S-hook") -> str:
    return os.environ.get("MARZ_SESSION", default)


def emit(event_type: str, subject_kind: str, subject_id: str, payload: dict) -> None:
    """Record the hook's own event. Never let audit break the hook itself:
    a failed emit is reported on stderr, not raised."""
    try:
        events.emit(event_type,
                    events.Actor(kind="agent", id=agent_id(), session=session_id()),
                    events.Subject(kind=subject_kind, id=subject_id), payload)
    except Exception as exc:
        print(f"hook event emit failed ({event_type}): {exc}", file=sys.stderr)


def allow(context: str | None = None, **extra: Any) -> NoReturn:
    out: dict = {}
    if context:
        out["hookSpecificOutput"] = {"additionalContext": context}
    out.update(extra)
    if out:
        print(json.dumps(out, ensure_ascii=False))
    raise SystemExit(0)


def block(reason: str, *, event_type: str = "policy.denied",
          subject_kind: str = "tool", subject_id: str = "unknown",
          payload: dict | None = None) -> NoReturn:
    emit(event_type, subject_kind, subject_id,
         {"reason": reason, "hook": Path(sys.argv[0]).name, **(payload or {})})
    print(json.dumps({
        "hookSpecificOutput": {"permissionDecision": "deny",
                               "permissionDecisionReason": reason},
        "decision": "block", "reason": reason,
    }, ensure_ascii=False))
    raise SystemExit(2)


def fail_closed(reason: str) -> NoReturn:
    """Infrastructure present but unreadable: halt, do not guess (§0 rule 6)."""
    block(f"fail-closed: {reason}", event_type="verify.failed",
          subject_kind="hook", subject_id=Path(sys.argv[0]).stem)


def now() -> str:
    return clock.iso()
