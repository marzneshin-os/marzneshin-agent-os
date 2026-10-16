#!/usr/bin/env python3
"""Antigravity Doctor Native MCP Server — JSON-RPC 2.0 stdio interface."""

import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(1, str(REPO / "scripts"))

from scripts.lib.antigravity_doctor import AntigravityDoctor

DOCTOR = AntigravityDoctor()

TOOLS = [
    {
        "name": "antigravity_diagnose",
        "description": "Diagnose Google Antigravity account eligibility, credential store health, and 403 Forbidden root causes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "token": {
                    "type": "string",
                    "description": "Optional raw token JSON string to validate",
                }
            },
        },
    },
    {
        "name": "antigravity_clean_credentials",
        "description": "Purge stale Antigravity credentials and lockfiles from OS credential store without asking for passwords.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dry_run": {
                    "type": "boolean",
                    "description": "Simulate deletion without modifying system",
                    "default": False,
                }
            },
        },
    },
    {
        "name": "antigravity_repair",
        "description": "Perform full environment recovery: clean credentials, remove locks, and provide structured re-auth instructions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dry_run": {
                    "type": "boolean",
                    "description": "Simulate repair without modifying system",
                    "default": False,
                }
            },
        },
    },
    {
        "name": "antigravity_check_eligibility",
        "description": "Check if an email domain is eligible for Antigravity individual tier (detects Google Workspace incompatibility).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "Google email address to inspect",
                }
            },
            "required": ["email"],
        },
    },
    {
        "name": "antigravity_status",
        "description": "Quick one-line health status of Antigravity session.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


def handle_call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "antigravity_diagnose":
        res = DOCTOR.diagnose(token_str=args.get("token"))
        return {"content": [{"type": "text", "text": json.dumps(res.to_dict(), indent=2)}]}
    elif name == "antigravity_clean_credentials":
        res = DOCTOR.clean(dry_run=args.get("dry_run", False))
        return {"content": [{"type": "text", "text": json.dumps(res.to_dict(), indent=2)}]}
    elif name == "antigravity_repair":
        res = DOCTOR.repair(dry_run=args.get("dry_run", False))
        return {"content": [{"type": "text", "text": json.dumps(res.to_dict(), indent=2)}]}
    elif name == "antigravity_check_eligibility":
        email = args.get("email", "")
        is_ws = DOCTOR.is_workspace_domain(email)
        payload = {
            "email": email,
            "is_workspace": is_ws,
            "eligible": not is_ws,
            "age_verification_url": DOCTOR.AGE_VERIFICATION_URL,
        }
        return {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}]}
    elif name == "antigravity_status":
        res = DOCTOR.diagnose()
        payload = {"status": res.status, "email": res.active_email}
        return {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}]}
    raise ValueError(f"Unknown tool: {name}")


def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        try:
            req = json.loads(line)
        except Exception:
            continue

        method = req.get("method")
        msg_id = req.get("id")

        if method == "tools/list":
            resp = {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        elif method == "tools/call":
            params = req.get("params", {})
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            try:
                out = handle_call_tool(tool_name, tool_args)
                resp = {"jsonrpc": "2.0", "id": msg_id, "result": out}
            except Exception as e:
                resp = {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32603, "message": str(e)}}
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        elif method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "antigravity-doctor-mcp", "version": "1.0.0"},
                },
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        elif method == "notifications/initialized":
            pass


if __name__ == "__main__":
    main()
