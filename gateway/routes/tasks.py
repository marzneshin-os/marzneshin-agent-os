"""Task management endpoints (§5.3: /v1/tasks)."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from scripts.lib import a2a
from ..store.task_store import get_task_store

router = APIRouter(prefix="/v1", tags=["tasks"])


class TaskSubmitRequest(BaseModel):
    envelope: Optional[dict[str, Any]] = None
    sender: Optional[str] = None
    to: Optional[str] = None
    capability: Optional[str] = None
    input: Optional[dict[str, Any]] = None
    input_provenance: Optional[list[dict[str, Any]]] = None
    priority: str = "normal"
    autonomy_requested: str = "L2"


class MessageSubmitRequest(BaseModel):
    sender: str
    content: Any


class CancelRequest(BaseModel):
    reason: str = Field(..., min_length=1)
    auto_rollback: bool = True


@router.post("/tasks", status_code=status.HTTP_202_ACCEPTED)
def create_task(req: TaskSubmitRequest, response: Response) -> dict:
    store = get_task_store()
    
    if req.envelope:
        env = req.envelope
        problems = a2a.validate_envelope(env)
        if problems:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Envelope failed schema validation: {'; '.join(problems)}"
            )
    else:
        if not (req.sender and req.to and req.capability and req.input is not None):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required fields: sender, to, capability, input"
            )
        prov = req.input_provenance or [{"field": "$.input", "source": "http_gateway", "trust": "internal"}]
        try:
            env = a2a.build_envelope(
                sender=req.sender,
                to=req.to,
                capability=req.capability,
                input=req.input,
                input_provenance=prov,
                priority=req.priority,
                transport="T3",
                autonomy_requested=req.autonomy_requested,
            )
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    task_record, is_replayed = store.admit_task(env)
    if is_replayed:
        response.status_code = status.HTTP_200_OK
        return {
            "status": task_record["state"],
            "task_id": task_record["task_id"],
            "replayed": True,
            "created_at": task_record["created_at"],
            "result": task_record.get("result"),
        }

    return {
        "status": "admitted",
        "task_id": task_record["task_id"],
        "replayed": False,
        "created_at": task_record["created_at"],
    }


@router.get("/tasks/{task_id}")
def get_task(task_id: str) -> dict:
    store = get_task_store()
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found")
    return {
        "task_id": task["task_id"],
        "state": task["state"],
        "created_at": task["created_at"],
        "updated_at": task["updated_at"],
        "history": task["history"],
        "messages_count": len(task["messages"]),
        "result": task.get("result"),
    }


@router.post("/tasks/{task_id}/messages")
def post_task_message(task_id: str, req: MessageSubmitRequest) -> dict:
    store = get_task_store()
    try:
        msg = store.add_message(task_id, req.sender, req.content)
        return {"status": "ok", "message": msg}
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found")


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str, req: CancelRequest) -> dict:
    store = get_task_store()
    try:
        task = store.update_state(task_id, "cancelled", detail=f"Cancelled: {req.reason}")
        return {
            "status": "cancelled",
            "task_id": task_id,
            "reason": req.reason,
            "auto_rollback": req.auto_rollback,
            "cancelled_at": task["updated_at"],
        }
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get("/tasks/{task_id}/events")
async def stream_task_events(task_id: str):
    store = get_task_store()
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found")

    async def event_generator():
        for ev in task["history"]:
            data = json.dumps({"event": "state_transition", "task_id": task_id, "data": ev})
            yield "data: " + data + "\n\n"
        
        if task["state"] in {"completed", "failed", "cancelled", "rolled_back", "crashed"}:
            data = json.dumps({"event": "close", "task_id": task_id, "final_state": task["state"]})
            yield "data: " + data + "\n\n"
            return

        last_count = len(task["history"])
        for _ in range(10):
            await asyncio.sleep(0.1)
            t = store.get_task(task_id)
            if t and len(t["history"]) > last_count:
                for ev in t["history"][last_count:]:
                    data = json.dumps({"event": "state_transition", "task_id": task_id, "data": ev})
                    yield "data: " + data + "\n\n"
                last_count = len(t["history"])
                if t["state"] in {"completed", "failed", "cancelled", "rolled_back", "crashed"}:
                    data = json.dumps({"event": "close", "task_id": task_id, "final_state": t["state"]})
                    yield "data: " + data + "\n\n"
                    break

    return StreamingResponse(event_generator(), media_type="text/event-stream")
