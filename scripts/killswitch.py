#!/usr/bin/env python3
"""Kill Switch for Marzneshin Autonomous OS Orchestration.

Commands:
    status  - Show current kill switch state
    stop    - Activate kill switch (halt all orchestration)
    resume  - Deactivate kill switch (allow orchestration)

Fail-closed: If state file is missing or corrupt, verdict = STOPPED.
"""
import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
STATE_FILE = PROJECT_ROOT / "state" / "STATE.json"
KILLSWITCH_FILE = PROJECT_ROOT / "state" / "killswitch.json"


def read_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def write_killswitch(verdict, reason=""):
    now = datetime.now(timezone.utc).isoformat()
    data = {
        "verdict": verdict,
        "updated_at": now,
        "reason": reason,
    }
    KILLSWITCH_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(KILLSWITCH_FILE, "w") as f:
        json.dump(data, f, indent=2)

    state = read_state()
    if state:
        state["kill_switch"]["verdict"] = verdict
        state["kill_switch"]["updated_at"] = now
        state["kill_switch"]["updated_by"] = "killswitch.py"
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)

    return data


def get_verdict():
    try:
        with open(KILLSWITCH_FILE, "r") as f:
            data = json.load(f)
            return data.get("verdict", "stopped")
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    state = read_state()
    if state and "kill_switch" in state:
        return state["kill_switch"].get("verdict", "stopped")

    return "stopped"


def cmd_status():
    verdict = get_verdict()
    state = read_state()
    phase = state.get("phase", "unknown") if state else "unknown"
    receipts = state.get("receipt_chain", {}).get("count", 0) if state else 0

    print(json.dumps({
        "verdict": verdict,
        "phase": phase,
        "receipt_count": receipts,
        "state_file": str(STATE_FILE),
        "state_exists": STATE_FILE.exists(),
    }, indent=2))

    return 0 if verdict == "running" else 1


def cmd_stop():
    reason = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "Manual stop"
    data = write_killswitch("stopped", reason)
    print(f"KILL SWITCH ACTIVATED: {json.dumps(data, indent=2)}")
    return 0


def cmd_resume():
    reason = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "Manual resume"
    data = write_killswitch("running", reason)
    print(f"KILL SWITCH DEACTIVATED: {json.dumps(data, indent=2)}")
    return 0


COMMANDS = {
    "status": cmd_status,
    "stop": cmd_stop,
    "resume": cmd_resume,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"Usage: {sys.argv[0]} {{status|stop|resume}} [reason]")
        print("\nFail-closed: missing state = STOPPED")
        return 1

    return COMMANDS[sys.argv[1]]()


if __name__ == "__main__":
    sys.exit(main())
