#!/usr/bin/env python3
"""Relevance AI account and resource manager.

Commands
--------
  health        Check current account health
  snapshot      Export all agents/tools/workforces to local blueprints
  deploy        Deploy blueprints to current account
  rotate        Auto-rotate to next healthy account
  add-account   Add a new account to the pool
  status        Show pool status with health for each account
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure lib is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import relevance_health as rh  # noqa: E402


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_health() -> None:
    """Check current account health."""
    account = rh._active_account()
    if not account:
        print("❌ No active account configured.")
        print("   Run: python3 scripts/relevance_manager.py add-account")
        sys.exit(1)

    status = rh.quick_check(account)
    label = account.get("label", "unknown")

    icons = {rh.HEALTHY: "✅", rh.LOW_CREDITS: "⚠️", rh.DEAD: "❌"}
    print(f"{icons[status]} Account '{label}' is {status}")

    if status == rh.DEAD:
        sys.exit(1)


def cmd_snapshot() -> None:
    """Snapshot all resources to local blueprints."""
    print("📸 Taking snapshot of current account...")
    result = rh.snapshot_all()
    if "error" in result:
        print(f"❌ Error: {result['error']}")
        sys.exit(1)

    print("✅ Snapshot complete:")
    print(f"   Agents:     {result['agents']}")
    print(f"   Tools:      {result['tools']}")
    print(f"   Workforces: {result['workforces']}")


def cmd_deploy() -> None:
    """Deploy blueprints to current account."""
    print("🚀 Deploying blueprints to current account...")
    result = rh.deploy_all()
    if "error" in result:
        print(f"❌ Error: {result['error']}")
        sys.exit(1)

    print("✅ Deploy complete:")
    print(f"   Agents:     {result['agents']}")
    print(f"   Tools:      {result['tools']}")
    print(f"   Workforces: {result['workforces']}")
    if result.get("errors"):
        print(f"   ⚠️  Errors ({len(result['errors'])}):")
        for e in result["errors"]:
            print(f"      • {e}")


def cmd_rotate() -> None:
    """Auto-rotate to next healthy account."""
    print("🔄 Auto-rotating to next healthy account...")
    result = rh.auto_rotate()

    if result["success"]:
        print(f"✅ Switched to account: {result['new_account']}")
        print("   .env updated automatically")
        d = result.get("deploy", {})
        print(f"   Deployed: {d.get('agents', 0)} agents, "
              f"{d.get('tools', 0)} tools, "
              f"{d.get('workforces', 0)} workforces")
    else:
        print(f"❌ Rotation failed: {result.get('error', 'Unknown error')}")
        if result.get("all_dead"):
            print("\n   ℹ️  All accounts exhausted. Add a new account:")
            print("   python3 scripts/relevance_manager.py add-account")
        sys.exit(1)


def cmd_add_account() -> None:
    """Add a new account to the pool."""
    print("➕ Add new Relevance AI account")
    print("   (Find these in Relevance AI → Settings → API Keys)\n")

    label = input("   Label (e.g. backup-1): ").strip()
    region = input("   Region (e.g. d7b62b): ").strip()
    project = input("   Project ID: ").strip()
    api_key = input("   API Key (sk-…): ").strip()

    if not all([label, region, project, api_key]):
        print("❌ All fields are required.")
        sys.exit(1)

    print("\n   Verifying credentials…")
    result = rh.add_account(label, region, project, api_key)

    if "error" in result:
        print(f"❌ {result['error']}")
        sys.exit(1)

    print(f"✅ Account '{label}' added (health: {result['health']})")
    print(f"   Pool now has {result['index'] + 1} account(s)")


def cmd_status() -> None:
    """Show pool status."""
    info = rh.pool_status()

    if info["total"] == 0:
        print("📋 Account Pool: EMPTY")
        print("   Run: python3 scripts/relevance_manager.py add-account")
        return

    icons = {rh.HEALTHY: "✅", rh.LOW_CREDITS: "⚠️", rh.DEAD: "❌"}
    print(f"📋 Account Pool ({info['total']} accounts)\n")

    for acc in info["accounts"]:
        marker = "→" if acc["active"] else " "
        icon = icons.get(acc["health"], "❓")
        print(f"  {marker} [{acc['index']}] {acc['label']}  "
              f"{icon} {acc['health']}")
        print(f"       Region: {acc['region']}  "
              f"Added: {acc['added_at']}")


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

COMMANDS = {
    "health":      cmd_health,
    "snapshot":    cmd_snapshot,
    "deploy":     cmd_deploy,
    "rotate":     cmd_rotate,
    "add-account": cmd_add_account,
    "status":     cmd_status,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        print("Commands:")
        for name, fn in COMMANDS.items():
            print(f"  {name:15s}  {fn.__doc__}")
        sys.exit(1 if len(sys.argv) >= 2 else 0)

    COMMANDS[sys.argv[1]]()


if __name__ == "__main__":
    main()
