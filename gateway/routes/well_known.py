"""Well-known discovery endpoint (§5.3: GET /.well-known/agent-card.json)."""

from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter
import yaml

from scripts.lib import paths

router = APIRouter()


@router.get("/.well-known/agent-card.json")
def get_host_agent_card() -> dict:
    card_path = paths.repo_root() / "agents" / "cards" / "orchestrator.yaml"
    if card_path.exists():
        with open(card_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if isinstance(data, dict):
                return data
    return {
        "id": "orchestrator",
        "name": "Orchestrator (CEO Agent)",
        "version": "2.0.0",
        "tier": 0,
        "capabilities": ["a2a.dispatch", "policy.evaluate"],
        "transports": {"preferred": "T1", "allowed": ["T1", "T2", "T3"]},
    }
