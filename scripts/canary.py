#!/usr/bin/env python3
"""Canary Rollout Mechanism for Marzneshin Autonomous OS.

Manages safe, staged configuration rollouts with automated verification and instant rollback.
Owned by: @config-engineer (L2 autonomy)

Workflow:
    1. STAGE: Stage candidate configuration, back up current production config, claim lease.
    2. VERIFY: Run sim harness and check health. If failure, trigger auto-rollback.
    3. PROMOTE: If verified, promote candidate to active production config and release lease.
    4. ROLLBACK: If any check fails or killswitch activates, restore backup and release lease.

Commands:
    stage   <service> <config_file>   - Stage canary configuration
    verify  <service>                 - Verify staged canary configuration
    promote <service>                 - Promote verified canary to production
    rollback <service>                - Roll back canary to pre-canary backup
    status                            - Show current canary status
"""
import json
import sys
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CONFIGS_DIR = PROJECT_ROOT / "configs"
CANARY_DIR = CONFIGS_DIR / "canary"
BACKUP_DIR = CONFIGS_DIR / "backups"
CANARY_STATE_FILE = CANARY_DIR / "canary_state.json"
EVENTS_DIR = PROJECT_ROOT / "state" / "events"


def ensure_dirs():
    CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
    CANARY_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)


def check_killswitch():
    """Fail-closed check against killswitch."""
    ks_script = PROJECT_ROOT / "scripts" / "killswitch.py"
    if ks_script.exists():
        res = subprocess.run([sys.executable, str(ks_script), "status"], capture_output=True, text=True)
        if "running" not in res.stdout:
            print("⛔ Kill switch active or unreadable! Aborting canary operations.")
            return False
    return True


def load_canary_state():
    ensure_dirs()
    if CANARY_STATE_FILE.exists():
        try:
            with open(CANARY_STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"active_canaries": {}, "history": []}


def save_canary_state(state):
    ensure_dirs()
    with open(CANARY_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def emit_event(event_type, description, metadata=None):
    now = datetime.now(timezone.utc)
    event_id = f"canary-{now.strftime('%Y%m%d%H%M%S')}"
    event = {
        "event_id": event_id,
        "timestamp": now.isoformat(),
        "agent": "agent-config-engineer",
        "type": event_type,
        "description": description,
        "metadata": metadata or {},
    }
    filename = f"{now.strftime('%Y%m%d-%H%M%S')}-{event_type}.json"
    with open(EVENTS_DIR / filename, "w") as f:
        json.dump(event, f, indent=2)
    return event


def cmd_stage(service, candidate_path):
    if not check_killswitch():
        return 1

    candidate_file = Path(candidate_path)
    if not candidate_file.exists():
        print(f"❌ Candidate config file not found: {candidate_path}")
        return 1

    state = load_canary_state()
    if service in state["active_canaries"]:
        print(f"⚠️ Service '{service}' already has an active canary in stage '{state['active_canaries'][service]['status']}'.")
        print("Run promote or rollback first.")
        return 1

    # Claim lease
    lease_script = PROJECT_ROOT / "scripts" / "lease.py"
    if lease_script.exists():
        subprocess.run([sys.executable, str(lease_script), "claim", "agent-config-engineer", f"config:{service}"])

    now = datetime.now(timezone.utc).isoformat()
    prod_target = CONFIGS_DIR / f"{service}.json"
    backup_file = BACKUP_DIR / f"{service}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"

    # Backup existing config if present
    has_backup = False
    if prod_target.exists():
        shutil.copy2(prod_target, backup_file)
        has_backup = True

    # Copy candidate to staging
    staged_file = CANARY_DIR / f"{service}.staged.json"
    shutil.copy2(candidate_file, staged_file)

    state["active_canaries"][service] = {
        "status": "staged",
        "staged_at": now,
        "candidate_file": str(staged_file),
        "backup_file": str(backup_file) if has_backup else None,
        "prod_target": str(prod_target),
    }
    save_canary_state(state)

    emit_event("task_started", f"Canary staged for service '{service}'", {"service": service, "candidate": str(candidate_path)})
    print(f"✅ Canary successfully staged for '{service}'. Run 'canary.py verify {service}' next.")
    return 0


def cmd_verify(service):
    if not check_killswitch():
        return 1

    state = load_canary_state()
    if service not in state["active_canaries"]:
        print(f"❌ No active canary for service '{service}'")
        return 1

    canary = state["active_canaries"][service]
    staged_path = Path(canary["candidate_file"])

    if not staged_path.exists():
        print(f"❌ Staged candidate missing: {staged_path}")
        cmd_rollback(service)
        return 1

    # Validate JSON syntax
    try:
        with open(staged_path, "r") as f:
            json.load(f)
    except Exception as e:
        print(f"❌ Canary config JSON invalid: {e}")
        cmd_rollback(service)
        return 1

    # Run sim harness if available
    harness_script = PROJECT_ROOT / "sim" / "harness.py"
    if harness_script.exists():
        print("🔍 Running simulation harness verification...")
        sim_res = subprocess.run([sys.executable, str(harness_script), "run", "orchestration-foundation"], capture_output=True, text=True)
        if sim_res.returncode != 0:
            print("❌ Simulation failed during canary verification:")
            print(sim_res.stdout)
            cmd_rollback(service)
            return 1
        print("  ✅ Simulation harness: GREEN")

    canary["status"] = "verified"
    canary["verified_at"] = datetime.now(timezone.utc).isoformat()
    save_canary_state(state)

    emit_event("verification_passed", f"Canary verification passed for '{service}'", {"service": service})
    print(f"✅ Canary verified for '{service}'. Ready for promotion ('canary.py promote {service}').")
    return 0


def cmd_promote(service):
    if not check_killswitch():
        return 1

    state = load_canary_state()
    if service not in state["active_canaries"]:
        print(f"❌ No active canary for service '{service}'")
        return 1

    canary = state["active_canaries"][service]
    if canary["status"] != "verified":
        print(f"⚠️ Canary is in status '{canary['status']}', not 'verified'. Run verify first.")
        return 1

    staged_path = Path(canary["candidate_file"])
    prod_target = Path(canary["prod_target"])

    shutil.copy2(staged_path, prod_target)
    staged_path.unlink(missing_ok=True)

    canary["status"] = "promoted"
    canary["promoted_at"] = datetime.now(timezone.utc).isoformat()
    state["history"].append(canary)
    del state["active_canaries"][service]
    save_canary_state(state)

    # Release lease
    lease_script = PROJECT_ROOT / "scripts" / "lease.py"
    if lease_script.exists():
        subprocess.run([sys.executable, str(lease_script), "release", "agent-config-engineer", f"config:{service}"])

    emit_event("task_completed", f"Canary promoted to production for '{service}'", {"service": service})
    print(f"🎉 Canary successfully PROMOTED to production for '{service}'!")
    return 0


def cmd_rollback(service):
    state = load_canary_state()
    if service not in state["active_canaries"]:
        print(f"ℹ️ No active canary found for '{service}'")
        return 0

    canary = state["active_canaries"][service]
    backup_file = canary.get("backup_file")
    prod_target = Path(canary["prod_target"])

    if backup_file and Path(backup_file).exists():
        shutil.copy2(backup_file, prod_target)
        print(f"↩️ Restored previous production config from {backup_file}")
    else:
        prod_target.unlink(missing_ok=True)
        print(f"↩️ Removed newly staged prod target: {prod_target}")

    staged_path = Path(canary["candidate_file"])
    staged_path.unlink(missing_ok=True)

    canary["status"] = "rolled_back"
    canary["rolled_back_at"] = datetime.now(timezone.utc).isoformat()
    state["history"].append(canary)
    del state["active_canaries"][service]
    save_canary_state(state)

    # Release lease
    lease_script = PROJECT_ROOT / "scripts" / "lease.py"
    if lease_script.exists():
        subprocess.run([sys.executable, str(lease_script), "release", "agent-config-engineer", f"config:{service}"])

    emit_event("task_failed", f"Canary rolled back for '{service}'", {"service": service})
    print(f"🛡️ Rollback complete for '{service}'. Production state safely restored.")
    return 0


def cmd_status():
    state = load_canary_state()
    print(json.dumps(state, indent=2))
    return 0


def main():
    ensure_dirs()
    if len(sys.argv) < 2:
        print("Usage: canary.py {stage|verify|promote|rollback|status} [args...]")
        return 1

    cmd = sys.argv[1]
    if cmd == "status":
        return cmd_status()
    elif cmd == "stage" and len(sys.argv) >= 4:
        return cmd_stage(sys.argv[2], sys.argv[3])
    elif cmd == "verify" and len(sys.argv) >= 3:
        return cmd_verify(sys.argv[2])
    elif cmd == "promote" and len(sys.argv) >= 3:
        return cmd_promote(sys.argv[2])
    elif cmd == "rollback" and len(sys.argv) >= 3:
        return cmd_rollback(sys.argv[2])
    else:
        print("Invalid command arguments.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
