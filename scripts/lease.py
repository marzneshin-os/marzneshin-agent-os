#!/usr/bin/env python3
"""Lease management for Marzneshin Autonomous OS Orchestration.

Commands:
    claim   <agent> <target>  - Claim a lease on a target
    release <agent> <target>  - Release a lease
    list                      - List all active leases
    reap                      - Remove expired leases (TTL: 1 hour)
"""
import json
import sys
import hashlib
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
LEASES_DIR = PROJECT_ROOT / "state" / "leases"
TTL_HOURS = 1


def generate_fencing_token(agent, target):
    now = datetime.now(timezone.utc).isoformat()
    raw = f"{agent}:{target}:{now}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def get_lease_file(agent, target):
    safe_agent = agent.replace("/", "-").replace("\\", "-")
    safe_target = target.replace("/", "-").replace("\\", "-")
    return LEASES_DIR / f"{safe_agent}--{safe_target}.json"


def find_lease_for_target(target):
    for lease_file in LEASES_DIR.glob("*.json"):
        if lease_file.name == "README.md":
            continue
        try:
            with open(lease_file, "r") as f:
                data = json.load(f)
            if data.get("target") == target:
                return lease_file, data
        except (json.JSONDecodeError, KeyError):
            continue
    return None, None


def cmd_claim():
    if len(sys.argv) < 4:
        print("Usage: lease.py claim <agent> <target>")
        return 1

    agent = sys.argv[2]
    target = sys.argv[3]

    existing_file, existing = find_lease_for_target(target)
    if existing:
        exp = datetime.fromisoformat(existing["expires_at"].replace("Z", "+00:00"))
        if exp > datetime.now(timezone.utc):
            print(json.dumps({
                "error": "LEASE_CONFLICT",
                "held_by": existing["agent"],
                "target": target,
                "expires_at": existing["expires_at"],
            }, indent=2))
            return 1

        existing_file.unlink()

    now = datetime.now(timezone.utc)
    token = generate_fencing_token(agent, target)
    lease = {
        "agent": agent,
        "target": target,
        "fencing_token": token,
        "claimed_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=TTL_HOURS)).isoformat(),
    }

    lease_file = get_lease_file(agent, target)
    LEASES_DIR.mkdir(parents=True, exist_ok=True)
    with open(lease_file, "w") as f:
        json.dump(lease, f, indent=2)

    print(json.dumps({"status": "CLAIMED", **lease}, indent=2))
    return 0


def cmd_release():
    if len(sys.argv) < 4:
        print("Usage: lease.py release <agent> <target>")
        return 1

    agent = sys.argv[2]
    target = sys.argv[3]

    lease_file = get_lease_file(agent, target)
    if not lease_file.exists():
        print(json.dumps({"status": "NOT_FOUND", "agent": agent, "target": target}, indent=2))
        return 1

    lease_file.unlink()
    print(json.dumps({"status": "RELEASED", "agent": agent, "target": target}, indent=2))
    return 0


def cmd_list():
    leases = []
    now = datetime.now(timezone.utc)

    for lease_file in LEASES_DIR.glob("*.json"):
        try:
            with open(lease_file, "r") as f:
                data = json.load(f)
            exp = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
            data["expired"] = exp < now
            leases.append(data)
        except (json.JSONDecodeError, KeyError):
            continue

    print(json.dumps({"active_leases": len(leases), "leases": leases}, indent=2))
    return 0


def cmd_reap():
    now = datetime.now(timezone.utc)
    reaped = []

    for lease_file in LEASES_DIR.glob("*.json"):
        try:
            with open(lease_file, "r") as f:
                data = json.load(f)
            exp = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
            if exp < now:
                reaped.append(data)
                lease_file.unlink()
        except (json.JSONDecodeError, KeyError, ValueError):
            continue

    print(json.dumps({"reaped": len(reaped), "leases": reaped}, indent=2))
    return 0


COMMANDS = {
    "claim": cmd_claim,
    "release": cmd_release,
    "list": cmd_list,
    "reap": cmd_reap,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"Usage: {sys.argv[0]} {{claim|release|list|reap}} [args]")
        return 1
    return COMMANDS[sys.argv[1]]()


if __name__ == "__main__":
    sys.exit(main())
