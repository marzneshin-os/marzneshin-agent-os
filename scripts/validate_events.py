#!/usr/bin/env python3
"""Event Schema Validator for Marzneshin Autonomous OS.

Validates event files in state/events/ against the canonical schema.
Creates properly formatted events with required fields.

Commands:
    validate           - Validate all events in state/events/
    create <type> <agent> <description> - Create a new event
    schema             - Print the event schema
"""
import json
import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
EVENTS_DIR = PROJECT_ROOT / "state" / "events"

REQUIRED_FIELDS = ["event_id", "timestamp", "agent", "type", "description"]
VALID_TYPES = [
    "phase_transition", "task_started", "task_completed", "task_failed",
    "lease_claimed", "lease_released", "lease_expired",
    "receipt_emitted", "killswitch_activated", "killswitch_resumed",
    "verification_passed", "verification_failed",
    "state_changed", "handoff_written",
]


def validate_event(filepath):
    errors = []
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [f"Invalid JSON: {e}"]

    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if "type" in data and data["type"] not in VALID_TYPES:
        errors.append(f"Invalid type '{data['type']}'. Valid: {VALID_TYPES}")

    return errors


def cmd_validate():
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    event_files = list(EVENTS_DIR.glob("*.json"))

    if not event_files:
        print("No event files to validate.")
        return 0

    total_errors = 0
    for ef in event_files:
        errors = validate_event(ef)
        if errors:
            print(f"❌ {ef.name}:")
            for e in errors:
                print(f"   - {e}")
            total_errors += len(errors)
        else:
            print(f"✅ {ef.name}: valid")

    print(f"\n{len(event_files)} events, {total_errors} errors")
    return 1 if total_errors > 0 else 0


def cmd_create():
    if len(sys.argv) < 5:
        print("Usage: validate_events.py create <type> <agent> <description>")
        return 1

    event_type = sys.argv[2]
    agent = sys.argv[3]
    description = " ".join(sys.argv[4:])

    if event_type not in VALID_TYPES:
        print(f"Invalid type '{event_type}'. Valid: {VALID_TYPES}")
        return 1

    now = datetime.now(timezone.utc)
    event_id = hashlib.sha256(f"{now.isoformat()}:{agent}:{event_type}".encode()).hexdigest()[:12]

    event = {
        "event_id": event_id,
        "timestamp": now.isoformat(),
        "agent": agent,
        "type": event_type,
        "description": description,
        "metadata": {},
    }

    filename = f"{now.strftime('%Y%m%d-%H%M%S')}-{event_type}.json"
    filepath = EVENTS_DIR / filename
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w") as f:
        json.dump(event, f, indent=2)

    print(f"✅ Created event: {filename}")
    print(json.dumps(event, indent=2))
    return 0


def cmd_schema():
    schema = {
        "required_fields": REQUIRED_FIELDS,
        "valid_types": VALID_TYPES,
        "example": {
            "event_id": "abc123def456",
            "timestamp": "2026-10-05T10:00:00+00:00",
            "agent": "claude-opus-4.6",
            "type": "phase_transition",
            "description": "Transitioned from P1 to P2",
            "metadata": {},
        },
    }
    print(json.dumps(schema, indent=2))
    return 0


COMMANDS = {"validate": cmd_validate, "create": cmd_create, "schema": cmd_schema}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"Usage: {sys.argv[0]} {{validate|create|schema}}")
        return 1
    return COMMANDS[sys.argv[1]]()


if __name__ == "__main__":
    sys.exit(main())
