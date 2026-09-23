"""Artifact management endpoints (§5.3: POST/GET /v1/artifacts[/{id}])."""

from __future__ import annotations

import base64
import json
from typing import Any
from fastapi import APIRouter, HTTPException, Request, status

from ..store.artifact_store import get_artifact_store

router = APIRouter(prefix="/v1", tags=["artifacts"])


@router.post("/artifacts", status_code=status.HTTP_201_CREATED)
async def upload_artifact(request: Request) -> dict:
    store = get_artifact_store()
    raw = await request.body()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty artifact content")
        
    content_type = request.headers.get("content-type", "")
    content = raw
    meta: dict[str, Any] = {"content_type": content_type}
    
    if "application/json" in content_type:
        try:
            parsed = json.loads(raw.decode("utf-8"))
            if isinstance(parsed, dict):
                if parsed.get("content_b64"):
                    content = base64.b64decode(parsed["content_b64"])
                elif parsed.get("text") is not None:
                    content = parsed["text"].encode("utf-8")
                if parsed.get("metadata"):
                    meta.update(parsed["metadata"])
        except Exception:
            pass  # Fall back to raw content
            
    res = store.store(content, meta)
    return {
        "status": "created",
        "artifact_id": res["artifact_id"],
        "hash": res["hash"],
        "size_bytes": res["size_bytes"],
    }


@router.get("/artifacts/{artifact_id}")
def get_artifact(artifact_id: str) -> dict:
    store = get_artifact_store()
    entry = store.retrieve(artifact_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Artifact {artifact_id} not found")
        
    content_bytes = entry["content"]
    try:
        text = content_bytes.decode("utf-8")
        is_text = True
    except UnicodeDecodeError:
        text = None
        is_text = False
        
    return {
        "artifact_id": entry["artifact_id"],
        "hash": entry["hash"],
        "size_bytes": entry["size_bytes"],
        "is_text": is_text,
        "text": text,
        "content_b64": base64.b64encode(content_bytes).decode("ascii") if not is_text else None,
        "metadata": entry["metadata"],
    }
