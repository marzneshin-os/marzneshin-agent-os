#!/usr/bin/env python3
"""AgentRouter Model Catalog & Failover Chain (ADR-033, connector subset).

Reduced variant of agentrouter_gateway for WSL-side MCP connector use:
model catalog and failover chain only, no HTTP forwarding surface.
The full dual-protocol gateway lives in the Windows checkout.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import clock

AGENTROUTER_MODELS: Dict[str, Dict[str, Any]] = {
    "gpt-6.1sol": {
        "id": "gpt-6.1sol",
        "name": "GPT-6.1 Sol (24/7 Unlimited)",
        "provider": "agentrouter",
        "unlimited": True,
        "release_windows_utc": [],
        "protocols": ["chat_completions", "responses", "anthropic_bridge"],
        "tier": "tier_0",
        "stateless_scrub": True,
        "description": "Unlimited flagship model; requires stateless scrub to prevent cross-node decryption failure.",
    },
    "gpt-6-astra": {
        "id": "gpt-6-astra",
        "name": "GPT-6 Astra (Apex Time-Window)",
        "provider": "agentrouter",
        "unlimited": False,
        "release_windows_utc": ["07:00-09:00", "19:00-21:00"],  # 15:00 & 03:00 Beijing Time
        "protocols": ["chat_completions", "responses", "anthropic_bridge"],
        "tier": "tier_0",
        "stateless_scrub": True,
        "description": "Apex frontier model supplied in 2-hour daily release windows (03:00 and 15:00 BJT).",
    },
    "claude-opus-5": {
        "id": "claude-opus-5",
        "name": "Claude Opus 5",
        "provider": "agentrouter",
        "unlimited": False,
        "release_windows_utc": [],
        "protocols": ["anthropic_messages", "chat_completions"],
        "tier": "tier_0",
        "stateless_scrub": False,
        "description": "Frontier Anthropic reasoning model.",
    },
    "claude-opus-4-8": {
        "id": "claude-opus-4-8",
        "name": "Claude Opus 4.8",
        "provider": "agentrouter",
        "unlimited": False,
        "release_windows_utc": [],
        "protocols": ["anthropic_messages", "chat_completions"],
        "tier": "tier_0",
        "stateless_scrub": False,
        "description": "Anthropic reasoning model fallback.",
    },
    "gpt-5.6-sol": {
        "id": "gpt-5.6-sol",
        "name": "GPT-5.6 Sol",
        "provider": "agentrouter",
        "unlimited": False,
        "release_windows_utc": [],
        "protocols": ["chat_completions", "responses", "anthropic_bridge"],
        "tier": "tier_0",
        "stateless_scrub": True,
        "description": "Frontier OpenAI-compatible fallback.",
    },
    "glm-5.3": {
        "id": "glm-5.3",
        "name": "GLM 5.3",
        "provider": "agentrouter",
        "unlimited": False,
        "release_windows_utc": [],
        "protocols": ["anthropic_messages", "chat_completions"],
        "tier": "tier_1",
        "stateless_scrub": False,
        "description": "Tier 1 high-velocity implementation model.",
    },
    "deepseek-v4-flash": {
        "id": "deepseek-v4-flash",
        "name": "DeepSeek V4 Flash",
        "provider": "agentrouter",
        "unlimited": False,
        "release_windows_utc": [],
        "protocols": ["anthropic_messages", "chat_completions"],
        "tier": "tier_2",
        "stateless_scrub": False,
        "description": "Tier 2 high-throughput mechanical execution and zero-rate fallback.",
    },
}


def get_failover_chain(requested_model: str, utc_now: Optional[datetime] = None) -> List[str]:
    """Compute ordered failover chain based on model tier and Astra UTC supply windows."""
    if utc_now is None:
        utc_now = clock.now()
    astra_active = utc_now.hour in (7, 8, 19, 20)

    if astra_active:
        priority_pool = [
            "gpt-6-astra",
            "gpt-6.1sol",
            "claude-opus-5",
            "gpt-5.6-sol",
            "glm-5.3",
            "deepseek-v4-flash",
        ]
    else:
        priority_pool = [
            "gpt-6.1sol",
            "claude-opus-5",
            "gpt-6-astra",
            "gpt-5.6-sol",
            "glm-5.3",
            "deepseek-v4-flash",
        ]

    chain = [requested_model]
    for model_id in priority_pool:
        if model_id not in chain and model_id in AGENTROUTER_MODELS:
            chain.append(model_id)
    return chain
