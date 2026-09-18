#!/usr/bin/env python3
"""Stop hook (BUILD-SPEC §7.2, Iron Rule 3).

A session is not over until the next one can start cleanly. Fails (exit != 0)
when:
  - HANDOFF.md is missing or was not refreshed during this session (Rule 3)
  - this agent still holds leases (a held lease blocks the next claimant and
    feeds the reaper a false crash in 90 minutes)
  - the session.ended event could not be recorded

The order matters: checks first, the closing event second, exit last.
"""

from __future__ import annotations

import os

import _common as H
from lib import clock, leases, paths


def main() -> None:
    data = H.read_stdin()
    agent = H.agent_id()
    problems: list[str] = []

    # 1. HANDOFF freshness. "Refreshed this session" = modified in the last
    #    6 hours — wider than a session, narrower than "yesterday's note".
    handoff = paths.handoff_file()
    if not handoff.exists():
        problems.append("state/HANDOFF.md does not exist (Iron Rule 3)")
    else:
        age_s = clock.now().timestamp() - handoff.stat().st_mtime
        if age_s > 6 * 3600:
            problems.append(f"state/HANDOFF.md was last written {int(age_s // 60)}m ago — "
                            f"rewrite it for this session before stopping (Iron Rule 3)")

    # 2. Outstanding leases held by this agent.
    held = [l for l in leases.list_all()
            if l.holder == f"agent:{agent}" and not l.expired()]
    for lease in held:
        problems.append(f"lease on {lease.workstream!r} still held (token "
                        f"{lease.fencing_token}) — release it: "
                        f"scripts/fsp.py release {lease.workstream} --agent {agent}")

    if problems and not data.get("stop_hook_active"):
        H.block("session cannot close cleanly:\n  - " + "\n  - ".join(problems),
                event_type="verify.failed", subject_kind="session",
                subject_id=H.session_id())

    # 3. The closing event. If the audit write fails, the session is not over.
    try:
        H.emit("session.ended", "session", H.session_id(),
               {"agent": agent, "handoff_fresh": not problems,
                "leases_released": len(held) == 0})
        
        # Record session end in AgentMemory
        try:
            from lib import agentmemory
            agentmemory.call_mcp_tool("memory_save", {"content": f"Session {H.session_id()} ended for agent {agent}. Handoff fresh: {not problems}. Leases released: {len(held) == 0}."})
        except Exception:
            pass

    except Exception as exc:
        H.fail_closed(f"could not record session.ended: {exc}")

    H.allow()


if __name__ == "__main__":
    main()
