"""In-memory and disk-cached Task Store for HTTP Gateway (§5.3, §5.4).

Maintains task state transitions conforming to §5.4:
created → admitted → queued → running → (awaiting_approval) → verifying
        → completed | failed | cancelled | rolled_back | crashed
"""

from __future__ import annotations

import threading
from typing import Any, Optional
from scripts.lib import clock, ids

VALID_STATES = {
    "created", "admitted", "queued", "running", "awaiting_approval",
    "verifying", "completed", "failed", "cancelled", "rolled_back", "crashed"
}

ALLOWED_TRANSITIONS = {
    "created": {"admitted", "cancelled", "failed"},
    "admitted": {"queued", "running", "cancelled", "failed"},
    "queued": {"running", "cancelled", "failed"},
    "running": {"awaiting_approval", "verifying", "completed", "failed", "cancelled", "crashed"},
    "awaiting_approval": {"running", "cancelled", "failed"},
    "verifying": {"completed", "failed", "rolled_back", "cancelled"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
    "rolled_back": set(),
    "crashed": set(),
}


class TaskStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[str, dict[str, Any]] = {}
        self._idempotency: dict[str, dict[str, Any]] = {}

    def admit_task(self, envelope: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        with self._lock:
            idem = envelope.get("idempotency") or {}
            key = idem.get("key")
            if key and key in self._idempotency:
                entry = self._idempotency[key]
                expires_at = entry.get("expires_at")
                if not expires_at or expires_at > clock.iso():
                    task_id = entry["task_id"]
                    if task_id in self._tasks:
                        return self._tasks[task_id], True

            task_id = envelope.get("task_id") or f"A2A-{ids.new_ulid()}"
            now = clock.iso()
            task_record = {
                "task_id": task_id,
                "state": "admitted",
                "envelope": envelope,
                "created_at": now,
                "updated_at": now,
                "history": [
                    {"state": "created", "timestamp": now, "detail": "Task received via HTTP Gateway"},
                    {"state": "admitted", "timestamp": now, "detail": "Task validated and admitted into gateway store"},
                ],
                "messages": [],
                "result": None,
                "error": None,
            }
            self._tasks[task_id] = task_record

            if key:
                ttl_s = idem.get("ttl_s", 0)
                expires = None
                if ttl_s > 0:
                    from datetime import timedelta
                    expires = clock.to_iso(clock.now() + timedelta(seconds=ttl_s))
                self._idempotency[key] = {
                    "task_id": task_id,
                    "stored_at": now,
                    "expires_at": expires,
                }

            return task_record, False

    def get_task(self, task_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            return self._tasks.get(task_id)

    def update_state(self, task_id: str, new_state: str, detail: str = "") -> dict[str, Any]:
        with self._lock:
            if task_id not in self._tasks:
                raise KeyError(f"Task {task_id} not found")
            task = self._tasks[task_id]
            current = task["state"]
            if new_state not in VALID_STATES:
                raise ValueError(f"Invalid state: {new_state}")
            if new_state not in ALLOWED_TRANSITIONS.get(current, set()):
                if new_state not in {"cancelled", "failed"}:
                    raise ValueError(f"Illegal transition from {current} to {new_state}")

            now = clock.iso()
            task["state"] = new_state
            task["updated_at"] = now
            task["history"].append({"state": new_state, "timestamp": now, "detail": detail})
            return task

    def add_message(self, task_id: str, sender: str, content: Any) -> dict[str, Any]:
        with self._lock:
            if task_id not in self._tasks:
                raise KeyError(f"Task {task_id} not found")
            task = self._tasks[task_id]
            msg = {
                "message_id": f"MSG-{ids.new_ulid()}",
                "sender": sender,
                "content": content,
                "timestamp": clock.iso(),
            }
            task["messages"].append(msg)
            task["updated_at"] = clock.iso()
            return msg

    def complete_task(self, task_id: str, result: Any) -> dict[str, Any]:
        with self._lock:
            if task_id not in self._tasks:
                raise KeyError(f"Task {task_id} not found")
            task = self._tasks[task_id]
            now = clock.iso()
            task["state"] = "completed"
            task["result"] = result
            task["updated_at"] = now
            task["history"].append({"state": "completed", "timestamp": now, "detail": "Completed successfully"})
            return task

    def list_tasks(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._tasks.values())[-limit:]


_TASK_STORE: Optional[TaskStore] = None


def get_task_store() -> TaskStore:
    global _TASK_STORE
    if _TASK_STORE is None:
        _TASK_STORE = TaskStore()
    return _TASK_STORE
