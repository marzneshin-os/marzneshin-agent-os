"""control_room_sync.py — Unidirectional Sync Engine for Control Room (BUILD-SPEC §9, VS-6).

Implements:
  1. GitHub -> Control Room unidirectional sync (every 60s / on event).
     Mirrors STATE.json, leases, receipts, and health baseline across the 5 Moxt workflows:
       - Control Room
       - Engineering
       - Growth & Revenue
       - Security & Gov
       - Knowledge
  2. Control Room -> GitHub reverse sync STRICTLY LIMITED to two exceptions (§9.5, I1):
       - Exception 1: Approval field (human granting L1/L0 approval)
       - Exception 2: Kill Switch status (K3 human kill switch toggle)
     No other field or state is ever reverse-synced, protecting GitHub as the single SSoT.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import clock, events, leases, paths, receipts, state
from .atomic import read_json, write_json_atomic

WORKFLOWS = [
    "Control Room",
    "Engineering",
    "Growth & Revenue",
    "Security & Gov",
    "Knowledge",
]

REVERSE_WHITELIST_FIELDS = frozenset({"Approval", "Kill Switch"})


class SyncError(RuntimeError):
    pass


def get_default_adapter() -> Any:
    from adapters.moxt import MoxtAdapter
    return MoxtAdapter()


def sync_github_to_control_room(adapter: Any = None) -> dict[str, Any]:
    """Mirror current GitHub state into Control Room workflows (§9.1 - §9.4)."""
    ad = adapter or get_default_adapter()
    synced_tasks: list[str] = []

    # 1. Read GitHub SSoT state
    s = state.read()
    active_slice = s.get("active_slice", "VS-6")
    kill_state = read_json(paths.state_dir() / "KILL", default={})
    is_killed = bool(kill_state.get("killed", False))

    # --- Workflow 1: Control Room (Approvals & Kill Switch) ---
    ks_status = "Engaged" if is_killed else "Clear"
    ad.execute(
        "upsert_task",
        {
            "task": "KILL-SWITCH-TASK",
            "title": "Global Kill Switch (K3)",
            "workflow": "Control Room",
            "status": "In Progress",
            "fields": {
                "Kill Switch": ks_status,
                "Slice": active_slice,
                "Autonomy Level": "L0",
            },
        },
    )
    synced_tasks.append("KILL-SWITCH-TASK")

    # Health Baseline task
    baseline = read_json(paths.state_dir() / "HEALTH-BASELINE.json", default={})
    gates = baseline.get("gates", {})
    ad.execute(
        "upsert_task",
        {
            "task": "HEALTH-BASELINE-TASK",
            "title": f"Health Baseline ({active_slice})",
            "workflow": "Control Room",
            "status": "Done",
            "fields": {
                "Slice": active_slice,
                "Tests Passed": gates.get("tests", {}).get("passed", 0),
                "Sim Passed": gates.get("sim", {}).get("passed", 0),
                "Baseline Saved": baseline.get("saved_at", ""),
            },
        },
    )
    synced_tasks.append("HEALTH-BASELINE-TASK")

    # --- Workflow 2: Engineering (Workstreams & Leases) ---
    for ws, ws_data in s.get("workstreams", {}).items():
        tid = f"WS-{ws}"
        lease_info = ws_data.get("lease") or {}
        holder = lease_info.get("holder") or "free"
        is_leased = holder != "free"
        status = "In Progress" if is_leased else "Done"

        # Chain head receipt info
        head_file = paths.receipt_head_file(ws)
        head_data = read_json(head_file, default={})

        ad.execute(
            "upsert_task",
            {
                "task": tid,
                "title": f"Workstream: {ws}",
                "workflow": "Engineering",
                "status": status,
                "fields": {
                    "Owner (agent)": holder,
                    "Slice": active_slice,
                    "Receipt ID": head_data.get("task_id", ""),
                    "Autonomy Level": "L2",
                },
            },
        )
        synced_tasks.append(tid)

    # --- Workflow 3: Security & Gov (ADRs & Policies) ---
    adr_files = list((paths.repo_root() / "decisions" / "ADR").glob("ADR-*.md"))
    latest_adrs = sorted(adr_files)[-5:]
    for adr_path in latest_adrs:
        tid = adr_path.stem
        ad.execute(
            "upsert_task",
            {
                "task": tid,
                "title": f"Decision: {adr_path.stem}",
                "workflow": "Security & Gov",
                "status": "Done",
                "fields": {
                    "Slice": active_slice,
                    "Autonomy Level": "L3",
                },
            },
        )
        synced_tasks.append(tid)

    # --- Workflow 4: Knowledge (Agent Cards & Specs) ---
    cards_dir = paths.agent_cards_dir()
    if cards_dir.exists():
        for card_path in cards_dir.glob("*.yaml"):
            tid = f"CARD-{card_path.stem}"
            ad.execute(
                "upsert_task",
                {
                    "task": tid,
                    "title": f"Agent Card: {card_path.stem}",
                    "workflow": "Knowledge",
                    "status": "Done",
                    "fields": {
                        "Slice": active_slice,
                        "Autonomy Level": "L3",
                    },
                },
            )
            synced_tasks.append(tid)

    return {
        "ok": True,
        "direction": "github_to_control_room",
        "synced_count": len(synced_tasks),
        "tasks": synced_tasks,
        "active_slice": active_slice,
        "timestamp": clock.iso(),
    }


def sync_control_room_to_github(
    adapter: Any = None,
    *,
    task_id: str | None = None,
    updated_fields: dict[str, Any] | None = None,
    actor_id: str = "control-room-sync",
) -> dict[str, Any]:
    """Reverse sync from Control Room -> GitHub STRICTLY LIMITED to two exceptions (§9.5, I1).

    Exception 1: Approval field.
    Exception 2: Kill Switch status.
    All other field modifications are rejected.
    """
    ad = adapter or get_default_adapter()
    applied: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    fields_to_check = updated_fields or {}

    # If no explicit fields passed, read from adapter
    if task_id and not updated_fields:
        if task_id == "KILL-SWITCH-TASK":
            res = ad.execute("read_killswitch_task", {})
            fields_to_check = {"Kill Switch": res.data.get("status", "Clear")}
        else:
            res = ad.execute("read_approval", {"task": task_id})
            fields_to_check = {"Approval": res.data.get("approval", "pending")}

    for f_name, f_val in fields_to_check.items():
        if f_name not in REVERSE_WHITELIST_FIELDS:
            # I1 VIOLATION PREVENTED: Refuse reverse sync
            rejected.append({
                "field": f_name,
                "value": f_val,
                "reason": f"field {f_name!r} is not in reverse sync whitelist (§9.5, I1); GitHub is sole SSoT"
            })
            continue

        # Exception 1: Approval
        if f_name == "Approval":
            if f_val.lower() == "granted":
                appr_dir = paths.state_dir() / "approvals"
                appr_dir.mkdir(parents=True, exist_ok=True)
                target_task = task_id or "GENERIC-APPROVAL"
                record = {
                    "task_id": target_task,
                    "approval": "granted",
                    "by": "owner:control-room",
                    "at": clock.iso(),
                }
                write_json_atomic(appr_dir / f"{target_task}.json", record)
                actor = events.Actor(kind="human", id="owner")
                events.emit(
                    "approval.granted",
                    actor,
                    events.Subject(kind="task", id=target_task),
                    {"channel": "control-room", "approval": "granted"}
                )
                applied.append({"field": f_name, "value": f_val, "action": "approval_recorded"})

        # Exception 2: Kill Switch (K3)
        elif f_name == "Kill Switch":
            from .killswitch import KillEntry, Scope, reconcile
            entries: list[KillEntry] = []
            if f_val.lower() in ("engaged", "killed"):
                entries.append(KillEntry(
                    scope=Scope.GLOBAL.value,
                    target=None,
                    reason=f"Control Room task status: {f_val}",
                    engaged_at=clock.iso(),
                    engaged_by="moxt:control-room",
                    source="K3",
                ))
            reconcile(
                external=entries,
                sources=["K3"],
                prune_sources=["K3"],
                verified_by="control-room",
            )
            applied.append({"field": f_name, "value": f_val, "action": f"killswitch_reconciled_{f_val.lower()}"})

    return {
        "ok": len(rejected) == 0,
        "applied": applied,
        "rejected": rejected,
        "timestamp": clock.iso(),
    }
