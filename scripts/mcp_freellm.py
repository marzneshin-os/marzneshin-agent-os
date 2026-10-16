#!/usr/bin/env python3
"""FreeLLMAPI Universal Free-Tier Token Pool Model Context Protocol (MCP) Server.

Exposes FreeLLMAPI multi-provider pool capabilities to AI coding agents (Antigravity, Claude Code, Cursor, OpenCode):
- freellm_pool_status: Inspect active, cooling, and configured keys across 34+ providers.
- freellm_list_models: Query free models filtered by task domain (coding, reasoning, fast, eval).
- freellm_test_provider: Probe latency and reachability of any free-tier provider.
- freellm_rotate_key: Force-rotate active API keys to circumvent per-key rate limits.

Architecture:
High-resilience Zero-Dependency JSON-RPC 2.0 stdio engine.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(WORKSPACE_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))

from lib.freellm_pool import (
    FreeLLMPoolManager,
    PROVIDER_CATALOG,
    SmartFallbackRouter,
    KeyVault,
    get_total_free_tier_capacity,
)
from adapters.freellm import FreeLLMAdapter
from lib import clock, ids

TOOLS_SPEC = [
    {
        "name": "freellm_pool_status",
        "description": "Inspect the operational status of the 34+ provider free-tier token pool (~7.4B monthly token capacity), active keys, and rate-limit cooldowns.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "freellm_list_models",
        "description": "List available free models and provider endpoints, optionally filtered by task domain (coding, reasoning, fast, eval, general).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "enum": ["coding", "reasoning", "fast", "eval", "general"],
                    "description": "Optional task domain filter",
                }
            },
        },
    },
    {
        "name": "freellm_test_provider",
        "description": "Probe a free-tier provider endpoint to test availability, latency, and active keys count.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "description": "Provider ID (e.g. groq, google_gemini, cerebras, mistral, sambanova)",
                }
            },
            "required": ["provider"],
        },
    },
    {
        "name": "freellm_rotate_key",
        "description": "Rotate the active API key for a specified provider to mitigate rate limits or key quota exhaustion.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "description": "Provider ID to rotate",
                }
            },
            "required": ["provider"],
        },
    },
]


def handle_tool_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "freellm_pool_status":
        pool = FreeLLMPoolManager()
        status = pool.get_full_pool_status()
        summary = (
            f"FreeLLMAPI Pool Status:\n"
            f"- Total Providers: {status['total_providers']}\n"
            f"- Active Keys: {status['active_keys']}\n"
            f"- Cooldown Keys: {status['cooldown_keys']}\n"
            f"- Combined Monthly Quota: {status['combined_monthly_tokens_estimate']:,} tokens (~7.4B)"
        )
        return {
            "content": [
                {"type": "text", "text": summary},
                {"type": "text", "text": json.dumps(status, indent=2)},
            ]
        }

    elif name == "freellm_list_models":
        domain = arguments.get("domain")
        matched = []
        for pid, p in PROVIDER_CATALOG.items():
            if domain and domain.lower() not in p.specialties:
                continue
            matched.append({
                "provider_id": pid,
                "provider_name": p.name,
                "models": p.models,
                "specialties": p.specialties,
                "monthly_quota": p.monthly_token_quota,
            })
        return {
            "content": [
                {"type": "text", "text": f"Found {len(matched)} matching providers for domain '{domain or 'all'}':"},
                {"type": "text", "text": json.dumps(matched, indent=2)},
            ]
        }

    elif name == "freellm_test_provider":
        provider = arguments.get("provider", "groq")
        adapter = FreeLLMAdapter()
        from datetime import timedelta
        res = adapter.execute(
            "test_provider",
            {"provider": provider},
            idem_key=ids.new_ulid(),
            idem_class="none",
            dry_run=False,
            deadline=clock.now() + timedelta(seconds=10),
            provenance=[],
        )
        if res.ok:
            return {"content": [{"type": "text", "text": f"Provider '{provider}' test PASSED: {json.dumps(res.data)}"}]}
        else:
            return {"content": [{"type": "text", "text": f"Provider '{provider}' test FAILED: {res.error}"}], "isError": True}

    elif name == "freellm_rotate_key":
        provider = arguments.get("provider", "groq")
        pool = FreeLLMPoolManager()
        new_key = pool.acquire_key(provider)
        redacted = KeyVault.redact(new_key)
        return {"content": [{"type": "text", "text": f"Rotated active key for provider [{provider}]: {redacted}"}]}

    return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}


def run_stdio_server() -> None:
    """Run JSON-RPC 2.0 stdio server loop."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "freellm-pool", "version": "1.0.0"},
                },
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "notifications/initialized":
            continue

        elif method == "tools/list":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": TOOLS_SPEC},
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            call_res = handle_tool_call(tool_name, tool_args)
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": call_res,
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "ping":
            resp = {"jsonrpc": "2.0", "id": req_id, "result": {}}
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        else:
            if req_id is not None:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()


if __name__ == "__main__":
    run_stdio_server()
