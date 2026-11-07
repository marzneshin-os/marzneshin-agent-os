#!/usr/bin/env python3
"""PreCompact hook for Claude Code (BUILD-SPEC §7.2, class A <3s).

Fired by Claude Code immediately before session compaction begins (e.g. idle compaction
at ~54m before 1h prompt cache expiration, or manual /compact).
Saves the live working context, active leases, fencing tokens, and in-flight task metadata
to state/checkpoints/claude_compact_{session_id}.json so that subsequent SessionStart with
matcher "compact" can restore full agent alignment seamlessly.
"""

from __future__ import annotations

import json
from pathlib import Path

import _common as H
from lib import leases, paths, state


def main() -> None:
    data = H.read_stdin()
    session_id = data.get("session_id") or H.session_id("S-compact")
    transcript_path = data.get("transcript_path")

    # Gather live system context
    s = state.read_or_empty()
    active_leases = [l.to_dict() for l in leases.list_all() if not l.expired()]

    # Extract last user input from transcript if provided
    last_user_query = ""
    if transcript_path and Path(transcript_path).is_file():
        try:
            with open(transcript_path, "r", encoding="utf-8") as tf:
                lines = tf.readlines()
                for line in reversed(lines[-30:]):
                    try:
                        record = json.loads(line)
                        if record.get("type") == "user" or record.get("role") == "user":
                            last_user_query = str(record.get("message") or record.get("content") or "")[:500]
                            break
                    except Exception:
                        continue
        except Exception:
            pass

    checkpoint = {
        "session_id": session_id,
        "saved_at": H.now(),
        "active_slice": s.get("active_slice"),
        "sense_level": s.get("sense_level", "Tick-A"),
        "open_tasks": s.get("open_tasks", []),
        "active_leases": active_leases,
        "last_user_query": last_user_query,
    }

    # Write checkpoint to state/checkpoints
    cp_dir = Path(H.REPO_ROOT) / "state" / "checkpoints"
    cp_dir.mkdir(parents=True, exist_ok=True)
    cp_file = cp_dir / f"claude_compact_{session_id}.json"
    cp_file.write_text(json.dumps(checkpoint, indent=2, ensure_ascii=False), encoding="utf-8")

    H.emit(
        "state.compacted",
        "session",
        session_id,
        {
            "source": "claude_idle_compaction",
            "checkpoint_path": paths.rel(cp_file),
            "active_leases_count": len(active_leases),
            "open_tasks_count": len(checkpoint["open_tasks"]),
        },
    )

    H.allow()


if __name__ == "__main__":
    main()
