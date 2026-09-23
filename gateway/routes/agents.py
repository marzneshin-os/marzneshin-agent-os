"""Agent Registry endpoint (§5.3: GET /v1/agents)."""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Query
from scripts.lib import a2a

router = APIRouter(prefix="/v1", tags=["agents"])


@router.get("/agents")
def list_agents(capability: Optional[str] = Query(None)) -> dict:
    reg = a2a.registry()
    agents = reg.get("agents", {})
    if capability:
        agents = {
            aid: info for aid, info in agents.items()
            if capability in info.get("capabilities", [])
        }
    return {
        "count": len(agents),
        "agents": agents,
        "capabilities": reg.get("capabilities", {}),
    }
