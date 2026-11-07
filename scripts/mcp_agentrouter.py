#!/usr/bin/env python3
"""AgentRouter Model Context Protocol (MCP) Server (ADR-033).

Exposes AgentRouter status, model catalog, harness config rendering,
and resilient failover route planning via JSON-RPC 2.0 stdio transport.
Zero external dependencies: pure Python 3 standard library.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(WORKSPACE_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))

from scripts.agentrouter_gateway import AGENTROUTER_MODELS, get_failover_chain
from scripts.agentrouter_sync_cli import HARNESS_TARGETS, render_config
from lib import clock

TOOLS_SPEC = [
    {
        "name": "agentrouter_status",
        "description": "Inspect AgentRouter mesh status, Astra UTC release window availability (03:00/15:00 BJT), and gateway metrics.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "agentrouter_models",
        "description": "List the 7 official AgentRouter models, supported protocols, model tiers, and stateless scrubbing requirements.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "agentrouter_render_config",
        "description": "Render ready-to-use production configuration for a specified coding agent harness (claude-code, codex, opencode, ccr, antigravity, etc.).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Target agent harness (e.g. claude-code, codex, opencode, ccr, antigravity, qwen, hermes, openclaw, pi, roo-cline)",
                },
                "use_local_gateway": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to point harness to local gateway (127.0.0.1:8787)",
                },
            },
            "required": ["target"],
        },
    },
    {
        "name": "agentrouter_route_plan",
        "description": "Generate an optimal primary model and fallback routing plan for a task given its complexity and current UTC hour.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_complexity": {
                    "type": "string",
                    "enum": ["critical", "high", "medium", "low"],
                    "description": "Complexity tier of the task",
                },
                "utc_hour": {
                    "type": "integer",
                    "description": "Optional UTC hour override (0-23) for simulating release windows",
                },
            },
            "required": ["task_complexity"],
        },
    },
]


def execute_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute requested MCP tool and return tool content structure."""
    if name == "agentrouter_status":
        now = clock.now()
        astra_active = now.hour in (7, 8, 19, 20)
        return {
            "gateway_version": "1.0.0 (ADR-033)",
            "upstream_base_url": os.environ.get("AGENTROUTER_BASE_URL", "https://agentrouter.org/v1"),
            "local_gateway_url": "http://127.0.0.1:8787",
            "utc_time": now.isoformat(),
            "astra_window_active": astra_active,
            "astra_supply_windows_utc": ["07:00-09:00", "19:00-21:00"],
            "astra_supply_windows_bjt": ["15:00-17:00", "03:00-05:00"],
            "recommended_flagship": "gpt-6-astra" if astra_active else "gpt-6.1sol",
            "models_count": len(AGENTROUTER_MODELS),
        }

    if name == "agentrouter_models":
        return {
            "models_count": len(AGENTROUTER_MODELS),
            "models": AGENTROUTER_MODELS,
        }

    if name == "agentrouter_render_config":
        target = str(arguments.get("target", "codex"))
        use_local = bool(arguments.get("use_local_gateway", True))
        try:
            rendered = render_config(target, use_local_gateway=use_local)
            return {
                "target": target,
                "use_local_gateway": use_local,
                "config": rendered,
            }
        except ValueError as err:
            return {"error": str(err), "supported_targets": HARNESS_TARGETS}

    if name == "agentrouter_route_plan":
        complexity = str(arguments.get("task_complexity", "medium")).lower()
        utc_hour_arg = arguments.get("utc_hour")
        now = clock.now()
        target_hour = int(utc_hour_arg) if utc_hour_arg is not None else now.hour
        mock_now = now.replace(hour=target_hour)
        astra_active = target_hour in (7, 8, 19, 20)

        if complexity in ("critical", "high"):
            apex_model = "gpt-6-astra" if astra_active else "gpt-6.1sol"
            tier = "tier_0"
        elif complexity == "medium":
            apex_model = "glm-5.3"
            tier = "tier_1"
        else:
            apex_model = "deepseek-v4-flash"
            tier = "tier_2"

        chain = get_failover_chain(apex_model, utc_now=mock_now)
        primary_meta = AGENTROUTER_MODELS.get(apex_model, {})

        return {
            "task_complexity": complexity,
            "simulated_utc_hour": target_hour,
            "astra_window_active": astra_active,
            "tier": tier,
            "primary_model": apex_model,
            "primary_protocols": primary_meta.get("protocols", ["chat_completions"]),
            "stateless_scrub_required": primary_meta.get("stateless_scrub", False),
            "failover_chain": chain,
        }

    return {"error": f"Unknown tool: '{name}'"}


def handle_jsonrpc(request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Process single JSON-RPC 2.0 request and return response."""
    method = request.get("method")
    req_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                },
                "serverInfo": {
                    "name": "agentrouter-mesh",
                    "version": "1.0.0",
                },
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": TOOLS_SPEC,
            },
        }

    if method == "tools/call":
        params = request.get("params", {})
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        tool_result = execute_tool(tool_name, tool_args)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(tool_result, indent=2),
                    }
                ],
            },
        }

    if req_id is not None:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: '{method}'",
            },
        }
    return None


def main() -> None:
    """Run standard input / output JSON-RPC processing loop."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        resp = handle_jsonrpc(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
