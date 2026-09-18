"""Moxt Control Room Adapter (BUILD-SPEC §4, §9, VS-6).

Translates Control Room operations into Moxt task workflows.
Supports local-first file-backed storage (state/control-room/tasks.json)
when no remote Moxt daemon is present, preserving the zero-external-secrets
discipline (GAP-REPORT-002 §2).
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from adapters.base import (
    Adapter,
    AdapterError,
    CircuitBreaker,
    Health,
    IdemClass,
    IdempotencyStore,
    Result,
    deadline_remaining_s,
)
from scripts.lib import clock, paths
from scripts.lib.atomic import read_json, write_json_atomic


class MoxtAdapter(Adapter):
    name = "moxt"
    CAPABILITIES = [
        "upsert_task",
        "assign_agent",
        "set_status",
        "set_field",
        "read_approval",
        "read_killswitch_task",
    ]

    def __init__(self, world: str = "prod"):
        self.world = world
        self._circuit = CircuitBreaker(threshold=5, reset_after_s=60.0)
        self._idem = IdempotencyStore()

    def _state_file(self) -> Path:
        p = paths.state_dir() / "control-room" / "tasks.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def _load_tasks(self) -> dict[str, dict[str, Any]]:
        sf = self._state_file()
        if not sf.exists():
            return {}
        return read_json(sf, default={})

    def _save_tasks(self, tasks: dict[str, dict[str, Any]]) -> None:
        write_json_atomic(self._state_file(), tasks)

    def healthz(self) -> Health:
        start = time.monotonic()
        try:
            self._circuit.before_call()
            # Verify state store is accessible
            _ = self._load_tasks()
            lat = (time.monotonic() - start) * 1000
            self._circuit.on_success()
            return Health(ok=True, detail="moxt-ready", latency_ms=round(lat, 2))
        except Exception as exc:
            self._circuit.on_failure()
            lat = (time.monotonic() - start) * 1000
            return Health(ok=False, detail=f"moxt-error: {exc}", latency_ms=round(lat, 2))

    def capabilities(self) -> list[str]:
        return list(self.CAPABILITIES)

    def execute(
        self,
        op: str,
        payload: dict,
        *,
        idem_key: str = "",
        idem_class: IdemClass = "scoped",
        dry_run: bool = False,
        deadline: datetime | None = None,
        provenance: list[dict] | None = None,
    ) -> Result:
        start = time.monotonic()
        if op not in self.CAPABILITIES:
            return Result(ok=False, op=op, error=f"unknown operation: {op}")

        # Idempotency check
        if idem_key and idem_class != "none":
            memo = self._idem.lookup(idem_key)
            if memo:
                return memo

        self._circuit.before_call()

        if deadline and deadline_remaining_s(deadline) <= 0:
            self._circuit.on_failure()
            raise AdapterError("deadline exceeded before call")

        try:
            tasks = self._load_tasks()
            data: dict[str, Any] = {}

            if op == "upsert_task":
                tid = payload.get("task") or payload.get("task_id")
                if not tid:
                    tid = f"T-moxt-{len(tasks) + 1:04d}"
                title = payload.get("title", "")
                workflow = payload.get("workflow", "Control Room")
                status = payload.get("status", "Backlog")
                fields = payload.get("fields", {})

                if not dry_run:
                    if tid in tasks:
                        tasks[tid].update({
                            "title": title or tasks[tid].get("title", ""),
                            "workflow": workflow or tasks[tid].get("workflow", "Control Room"),
                            "updated_at": clock.iso(),
                        })
                        tasks[tid]["fields"].update(fields)
                    else:
                        tasks[tid] = {
                            "task_id": tid,
                            "title": title,
                            "workflow": workflow,
                            "status": status,
                            "fields": fields,
                            "created_at": clock.iso(),
                            "updated_at": clock.iso(),
                        }
                    self._save_tasks(tasks)
                data = {"task": tid, "workflow": workflow, "status": status}

            elif op == "assign_agent":
                tid = payload.get("task")
                agent = payload.get("agent")
                if not tid:
                    raise AdapterError("missing required 'task' param")
                if not dry_run and tid in tasks:
                    tasks[tid]["fields"]["Owner (agent)"] = agent
                    tasks[tid]["updated_at"] = clock.iso()
                    self._save_tasks(tasks)
                data = {"task": tid, "agent": agent, "dispatched": True}

            elif op == "set_status":
                tid = payload.get("task")
                status = payload.get("status", "In Progress")
                if not tid:
                    raise AdapterError("missing required 'task' param")
                if not dry_run and tid in tasks:
                    tasks[tid]["status"] = status
                    tasks[tid]["updated_at"] = clock.iso()
                    self._save_tasks(tasks)
                data = {"task": tid, "status": status}

            elif op == "set_field":
                tid = payload.get("task")
                field_name = payload.get("field")
                val = payload.get("value")
                if not tid or not field_name:
                    raise AdapterError("missing required 'task' or 'field' param")
                if not dry_run and tid in tasks:
                    tasks[tid]["fields"][field_name] = val
                    tasks[tid]["updated_at"] = clock.iso()
                    self._save_tasks(tasks)
                data = {"task": tid, "field": field_name, "value": val}

            elif op == "read_approval":
                tid = payload.get("task")
                task = tasks.get(tid, {})
                approval = task.get("fields", {}).get("Approval", "pending")
                data = {"task": tid, "approval": approval}

            elif op == "read_killswitch_task":
                ks_task = tasks.get("KILL-SWITCH-TASK", {})
                status = ks_task.get("status", "Clear")
                data = {"status": status}

            elif op == "list_tasks":
                workflow = payload.get("workflow")
                items = list(tasks.values())
                if workflow:
                    items = [t for t in items if t.get("workflow") == workflow]
                data = {"tasks": items, "count": len(items)}

            dur = (time.monotonic() - start) * 1000
            res = Result(ok=True, op=op, data=data, dry_run=dry_run, duration_ms=dur)
            self._circuit.on_success()

            if idem_key and idem_class != "none":
                self._idem.save(idem_key, res, klass=idem_class)

            return res

        except Exception as exc:
            self._circuit.on_failure()
            dur = (time.monotonic() - start) * 1000
            return Result(ok=False, op=op, error=str(exc), duration_ms=dur)

    def rollback(self, receipt_ref: str) -> Result:
        return Result(ok=True, op="rollback", data={"receipt_ref": receipt_ref})
