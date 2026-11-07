#!/usr/bin/env python3
"""Notification hook (Anthropic claude-code-setup standard).

Fires when Claude Code issues notifications:
  - permission_prompt: Claude needs permission for a tool
  - idle_prompt: Claude waiting for user input (60+ seconds idle)
  - auth_success: Authentication succeeds
  - elicitation_dialog: MCP tool needs input

Logs notifications to logs/notifications.log and rings terminal bell for prompts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import _common as H

def main() -> None:
    data = H.read_stdin()
    matcher = data.get("matcher", "") or data.get("type", "")
    message = data.get("message", "") or data.get("content", "")

    # Ensure logs directory exists
    log_file = Path(H.REPO_ROOT) / "logs" / "notifications.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    ts = H.clock.iso()
    log_entry = {
        "timestamp": ts,
        "matcher": matcher,
        "message": message,
        "agent": H.agent_id(),
    }

    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except OSError:
        pass

    # Ring bell on permission or idle prompts so developer is notified
    if matcher in ("permission_prompt", "idle_prompt"):
        sys.stderr.write(f"\a[Claude Code Notification: {matcher}] {message}\n")
        sys.stderr.flush()

    H.allow()

if __name__ == "__main__":
    main()
