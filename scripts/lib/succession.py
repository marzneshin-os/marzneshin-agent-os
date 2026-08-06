"""succession — the executable §11.1 protocol (VS-4).

BUILD-SPEC §11.1 defines the flow; this module IS the flow. Both the CLI
(scripts/succession.py) and the sim actor (sim/actors.py SuccessionActor)
drive this one implementation — shared logic lives in lib, callers are thin
(CLAUDE.md §5).

    TRIGGER     member removed | lease expired | heartbeats missed | offboarding
    STEP 1 FREEZE       in-flight work -> abandoned receipt; lease revoked with
                        a fresh fencing token (the dead holder's writes die even
                        if its process wakes up)
    STEP 2 REVOKE       access removed: registry entry marked revoked (A2A scope
                        fails closed from that moment — lib/a2a.agent_entry)
    STEP 3 RECONSTRUCT  the member's state is rebuilt from the receipt chain +
                        event log ALONE — never from anyone's memory
    STEP 4 REASSIGN     successor by standby_for designation, else capability
                        match, else a pool standby inheriting the role — always
                        one autonomy level lower (§10.5)
    STEP 5 VERIFY       smoke: successor routable, receipt chain valid,
                        workstream claimable; fail-closed on any miss
    STEP 6 REPORT       artifact in artifacts/succession/ + events per step

(BACKFILL — receipts -> runbook — is Docs & Knowledge's job and stays out of
the automated flow; the report names it as a follow-up, §11.1 STEP 5.)

Member removal is NOT a crash: FREEZE closes open tasks as `abandoned`, so
crash_rate does not move for an administrative removal (ADR-007's window is
for sessions that die, not for members the organisation removes).

dry_run computes the whole flow and changes nothing — not even the event log
(same contract as reaper.py --dry-run).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from . import clock, events, ids, leases, paths, receipts
from .atomic import read_json, read_ndjson, write_json_atomic

TRIGGERS = frozenset({
    "member_removed", "lease_expired", "heartbeat_missed",
    "offboarding_flag", "consecutive_failures",
})

STEP_ORDER = ("FREEZE", "REVOKE", "RECONSTRUCT", "REASSIGN", "VERIFY", "REPORT")

_AUTONOMY = ("L0", "L1", "L2", "L3", "L4")
_TERMINAL_TASK_EVENTS = ("task.completed", "task.failed", "task.crashed",
                         "task.abandoned")


class SuccessionError(RuntimeError):
    pass


@dataclass
class Step:
    name: str
    ok: bool
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"step": self.name, "ok": self.ok, **self.detail}


def _actor_for(by: str, actor: events.Actor | None) -> events.Actor:
    return actor or events.Actor(kind="system", id=by)


def _open_tasks_of(agent: str, world: str) -> list[dict]:
    """STEP 3 input: task.started without a terminal event, per holder — from
    the event log, never from STATE (which may be stale or gone)."""
    base = paths.state_dir() / "events"
    if world == "sim":
        base = base / "sim"
    started: dict[str, dict] = {}
    terminal: set[str] = set()
    if base.exists():
        for day_dir in sorted(base.glob("2*/")):
            for f in sorted(day_dir.glob("*.ndjson")):
                for ev in read_ndjson(f):
                    if ev.get("type") == "task.started":
                        started[ev["subject"]["id"]] = {
                            "task_id": ev["subject"]["id"],
                            "holder": ev["actor"]["id"], "ts": ev.get("ts", "")}
                    elif ev.get("type") in _TERMINAL_TASK_EVENTS:
                        terminal.add(ev["subject"]["id"])
    holder_variants = {agent, f"agent:{agent}"}
    return [s for tid, s in sorted(started.items())
            if tid not in terminal and s["holder"] in holder_variants]


def _autonomy_lower(level: str) -> str:
    try:
        return _AUTONOMY[max(_AUTONOMY.index(level) - 1, 0)]
    except ValueError:
        return "L1"


def _autonomy_num(level: str) -> int:
    try:
        return _AUTONOMY.index(level)
    except ValueError:
        return -1


def _emit(ev: str, actor: events.Actor, subject: events.Subject,
          payload: dict, *, dry_run: bool) -> None:
    if not dry_run:
        events.emit(ev, actor, subject, payload, trust="internal")


def run(*, agent: str, workstream: str, trigger: str, by: str = "succession",
        reason: str = "", dry_run: bool = False,
        actor: events.Actor | None = None,
        on_abandoned: Callable[[str], None] | None = None) -> dict:
    """Execute the §11.1 flow. Returns the report dict (also the REPORT
    artifact body). Fail-closed: a step that cannot complete records
    succession.failed and stops the flow — it is never silently skipped."""
    if trigger not in TRIGGERS:
        raise SuccessionError(
            f"unknown trigger {trigger!r}; allowed: {sorted(TRIGGERS)}")
    a = _actor_for(by, actor)
    subject = events.Subject(kind="agent", id=agent)
    world = paths.current_world()
    steps: list[Step] = [Step("TRIGGER", True, {"trigger": trigger, "agent": agent,
                                                "workstream": workstream,
                                                "reason": reason})]
    report: dict[str, Any] = {
        "schema_version": "2.0.0",
        "agent": agent, "workstream": workstream, "trigger": trigger,
        "reason": reason, "by": by, "world": world, "dry_run": dry_run,
        "started_at": clock.iso(), "steps": [], "ok": False,
    }

    def _fail(step: Step, message: str) -> dict:
        step.ok = False
        step.detail["error"] = message
        report["steps"] = [s.to_dict() for s in steps]
        report["error"] = f"{step.name}: {message}"
        _emit("succession.failed", a, subject,
              {"step": step.name, "error": message, "trigger": trigger},
              dry_run=dry_run)
        return report

    _emit("member.removed", a, subject,
          {"trigger": trigger, "workstream": workstream, "reason": reason},
          dry_run=dry_run)
    _emit("succession.started", a, subject,
          {"trigger": trigger, "workstream": workstream, "reason": reason},
          dry_run=dry_run)

    # --- STEP 1 FREEZE -------------------------------------------------------
    step = Step("FREEZE", True)
    try:
        open_tasks = _open_tasks_of(agent, world)
        abandoned: list[str] = []
        for t in open_tasks:
            task_id = t["task_id"]
            if receipts.read(task_id):
                continue  # receipt exists; nothing to close (idempotent)
            if not dry_run:
                receipts.write(receipts.Receipt(
                    task_id=task_id, agent=agent, workstream=workstream,
                    status=receipts.Status.ABANDONED,
                    autonomy_level="unknown",
                    intent="(interrupted — member removed mid-task)",
                    reason=(f"succession FREEZE ({trigger}): task closed as "
                            f"abandoned — an administrative removal is not a "
                            f"crash, so crash_rate must not move for it"),
                    started_at=t.get("ts") or clock.iso(),
                    inputs_hash=ids.sha256_str(f"succession:abandoned:{task_id}"),
                    handoff_note=("Closed by the succession protocol (§11.1 STEP 1), "
                                  "not by the worker. State touched by this task is "
                                  "unverified until the successor re-checks it (STEP 3)."),
                    verification=[receipts.Verification(
                        check="succession.freeze", result="fail",
                        evidence="open task reconstructed from the event log; "
                                 "no terminal event exists",
                        verifier="lib.succession", independent_of_author=True)],
                ), strict=False)
                if on_abandoned:
                    on_abandoned(task_id)
            abandoned.append(task_id)
        burned = None
        lease = leases.read(workstream)
        if lease is not None and lease.holder in (agent, f"agent:{agent}"):
            if not dry_run:
                burned = leases.revoke(workstream, revoked_by=by,
                                       reason=f"succession ({trigger}): {reason}")
            else:
                burned = "(dry-run)"
        step.detail.update({"abandoned_tasks": abandoned,
                            "lease_found": lease is not None,
                            "burned_fencing_token": burned})
        steps.append(step)
        _emit("succession.frozen", a, subject, step.detail, dry_run=dry_run)
    except Exception as exc:  # noqa: BLE001 — recorded, never hidden
        steps.append(step)
        return _fail(step, f"{type(exc).__name__}: {exc}")

    # --- STEP 2 REVOKE -------------------------------------------------------
    step = Step("REVOKE", True)
    try:
        reg_path = paths.registry_file()
        reg = read_json(reg_path, default=None)
        if not isinstance(reg, dict) or "agents" not in reg:
            raise SuccessionError(f"registry unreadable at {paths.rel(reg_path)}")
        entry = reg["agents"].get(agent)
        if entry is None:
            raise SuccessionError(f"agent {agent!r} not in registry")
        if not dry_run:
            entry["revoked"] = True
            entry["revoked_at"] = clock.iso()
            entry["revoked_by"] = by
            write_json_atomic(reg_path, reg)
            from lib import a2a  # lazy: keeps the lib import DAG flat
            a2a.clear_registry_cache()
        step.detail.update({"registry": paths.rel(reg_path), "a2a_scope": "revoked",
                            "note": "secret rotation + Control Room/GitHub access "
                                    "removal are Owner-side effects; recorded as "
                                    "follow-ups in the report"})
        steps.append(step)
        _emit("succession.revoked", a, subject, step.detail, dry_run=dry_run)
    except Exception as exc:  # noqa: BLE001
        steps.append(step)
        return _fail(step, f"{type(exc).__name__}: {exc}")

    # --- STEP 3 RECONSTRUCT --------------------------------------------------
    step = Step("RECONSTRUCT", True)
    try:
        member_receipts = [r for r in receipts.list_all()
                           if r.get("agent") == agent]
        reconstruction = {
            "source": "receipt chain + event log only (§11.1 STEP 3)",
            "receipts_total": len(member_receipts),
            "last_receipts": [r.get("task_id") for r in member_receipts[-3:]],
            "open_tasks_closed": steps[1].detail.get("abandoned_tasks", []),
        }
        step.detail.update(reconstruction)
        steps.append(step)
        _emit("succession.reconstructed", a, subject, step.detail, dry_run=dry_run)
    except Exception as exc:  # noqa: BLE001
        steps.append(step)
        return _fail(step, f"{type(exc).__name__}: {exc}")

    # --- STEP 4 REASSIGN -----------------------------------------------------
    step = Step("REASSIGN", True)
    try:
        reg = read_json(reg_path, default=reg)  # re-read (REVOKE amended it)
        agents = reg.get("agents", {})
        removed_entry = agents.get(agent, {})
        removed_caps = set(removed_entry.get("capabilities", []))
        predecessor_autonomy = removed_entry.get("autonomy_max", "L2")
        successor_autonomy = _autonomy_lower(predecessor_autonomy)
        # 1) an explicit standby_for designation for this member wins (§10.5);
        # 2) else the best capability match among live agents;
        # 3) else a pool standby entry inheriting the role.
        designated = [name for name, e in agents.items()
                      if e.get("standby_for") == agent and not e.get("revoked")]
        capable = sorted(
            (name for name, e in agents.items()
             if name != agent and not e.get("revoked")
             and removed_caps & set(e.get("capabilities", []))),
            key=lambda n: -len(removed_caps & set(agents[n].get("capabilities", []))))
        if designated:
            successor, via = designated[0], "standby_for"
        elif capable:
            successor, via = capable[0], "capability_match"
        else:
            successor, via = f"{agent}-standby", "pool_standby"
        if successor not in agents:
            if not dry_run:
                agents[successor] = {
                    "role": f"pool standby for removed member {agent} (§11.1 REASSIGN)",
                    "capabilities": sorted(removed_caps),
                    "autonomy_max": successor_autonomy,
                    "transports": removed_entry.get("transports",
                                                  {"preferred": "T1", "allowed": ["T1"]}),
                    "moxt_agent": None,
                    "owns": removed_entry.get("owns", []),
                    "standby_for": agent,
                }
                write_json_atomic(reg_path, reg)
                from lib import a2a
                a2a.clear_registry_cache()
        step.detail.update({
            "successor": successor, "via": via,
            "autonomy": _autonomy_num(successor_autonomy),
            "autonomy_max": successor_autonomy,
            "predecessor_autonomy": _autonomy_num(predecessor_autonomy),
            "predecessor_autonomy_max": predecessor_autonomy,
            "note": "successor works one autonomy level lower (§10.5)"})
        steps.append(step)
        _emit("succession.reassigned", a, subject, step.detail, dry_run=dry_run)
    except Exception as exc:  # noqa: BLE001
        steps.append(step)
        return _fail(step, f"{type(exc).__name__}: {exc}")

    # --- STEP 5 VERIFY -------------------------------------------------------
    step = Step("VERIFY", True)
    try:
        checks: dict[str, bool] = {}
        reg = read_json(reg_path, default=reg)
        succ_entry = reg.get("agents", {}).get(successor) or {}
        routable = bool(succ_entry) and not succ_entry.get("revoked")
        if dry_run and not routable:
            # REASSIGN was simulated: a pool standby would exist by now.
            routable = steps[4].detail.get("via") == "pool_standby"
        checks["successor_routable"] = routable
        chain = receipts.verify_chain()
        checks["receipt_chain_ok"] = bool(chain.get("ok"))
        lease_now = leases.read(workstream)
        holder_ok = (lease_now is None
                     or lease_now.holder in (successor, f"agent:{successor}"))
        if dry_run and not holder_ok and lease_now is not None:
            # FREEZE was simulated: the removed member's lease would be
            # revoked by now, so project the would-be state.
            holder_ok = lease_now.holder in (agent, f"agent:{agent}")
        checks["workstream_free_or_successor"] = holder_ok
        step.detail.update({"checks": checks, "smoke": all(checks.values())})
        if dry_run:
            step.detail["projection"] = ("dry-run: checks evaluated against the "
                                         "would-be end state")
        step.ok = all(checks.values())
        steps.append(step)
        _emit("succession.verified", a, subject, step.detail, dry_run=dry_run)
        if not step.ok:
            return _fail(step, "smoke check failed — workstream stays at L1 "
                               "until a human re-verifies (§11.1 STEP 6)")
    except Exception as exc:  # noqa: BLE001
        steps.append(step)
        return _fail(step, f"{type(exc).__name__}: {exc}")

    # --- STEP 6 REPORT -------------------------------------------------------
    step = Step("REPORT", True)
    report["reassignment"] = steps[4].detail
    report["reconstruction"] = steps[3].detail
    report["follow_ups"] = [
        "BACKFILL: Docs & Knowledge converts the knowledge gap from receipts "
        "into the runbook (§11.1 STEP 5 — human/Docs lane, not automated)",
        "Owner: rotate any secrets the member touched; remove Control Room / "
        "GitHub access (REVOKE covers the repo-side A2A scope only)",
        "Owner: update CODEOWNERS if the member owned a human path",
        "ADR if this succession changed an architectural assumption",
    ]
    report["ok"] = True
    report["completed_at"] = clock.iso()
    report["steps"] = [s.to_dict() for s in [*steps, step]]
    try:
        if not dry_run:
            out = paths.artifacts_dir() / "succession" / (
                f"{clock.now().strftime('%Y-%m-%dT%H%M%SZ')}-{paths.slug(agent)}.json")
            step.detail["artifact"] = paths.rel(out)
            report["steps"][-1] = step.to_dict()
            write_json_atomic(out, report)
        steps.append(step)
        _emit("succession.completed", a, subject,
              {"successor": successor, "verify": steps[5].detail.get("checks"),
               "artifact": step.detail.get("artifact"), "trigger": trigger},
              dry_run=dry_run)
    except Exception as exc:  # noqa: BLE001
        steps.append(step)
        return _fail(step, f"{type(exc).__name__}: {exc}")

    return report
