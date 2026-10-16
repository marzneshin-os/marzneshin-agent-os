#!/usr/bin/env python3
"""Laya & Jev Typed Decisions Universal Model Context Protocol (MCP) Server.

Exposes non-autoregressive System 1 decision engine and Jev+Claude stacking capabilities
as standard MCP tools for Antigravity IDE, Claude Code, Cursor, OpenCode, and Codex.

Tools:
- laya_status: Inspect engine health, active provider (Jev API / Laya-MLX / Local), latency, and model info.
- laya_classify_intent: Fast categorical triage across discrete candidate categories (<15ms, 0 tokens).
- laya_guardrail_check: High-confidence policy and injection safety gating (P(violation), boolean is_safe).
- laya_score_rubric: Scalar rubric scoring for code safety, quality gates, and risk levels.
- laya_stacking_evaluate: Evaluate System 1 fast-pass vs System 2 escalation with threshold tau (440x cheaper).
- laya_typed_decision: Execute arbitrary typed questions (choice, score, noul) in a single forward pass.

Architecture:
High-resilience Zero-Dependency JSON-RPC 2.0 stdio engine.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(WORKSPACE_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))

from adapters.laya import LayaAdapter
from lib import clock
from lib.stacking import evaluate_stack

TOOLS_SPEC = [
    {
        "name": "laya_status",
        "description": "Inspect the status of the Laya / TypeSafe Jev System 1 Decision Engine, active provider mode, latency, and memory footprint.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "laya_classify_intent",
        "description": "Perform sub-15ms non-autoregressive intent classification over candidate categories with calibrated probabilities and confidence (0 tokens).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The input text or task description to classify."
                },
                "categories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of target category names (e.g. ['coder', 'reviewer', 'infra', 'billing'])."
                }
            },
            "required": ["text", "categories"]
        }
    },
    {
        "name": "laya_guardrail_check",
        "description": "Evaluate input text or shell commands for safety violations, policy bypass, or prompt injections using non-autoregressive noul head.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The text, prompt, or command to validate."
                }
            },
            "required": ["text"]
        }
    },
    {
        "name": "laya_score_rubric",
        "description": "Score input code diff or text against an ordered rubric scale (e.g. ['poor', 'acceptable', 'excellent']) returning scalar score and level.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The code diff or text to evaluate."
                },
                "rubric": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ordered rubric levels from lowest to highest."
                }
            },
            "required": ["text", "rubric"]
        }
    },
    {
        "name": "laya_stacking_evaluate",
        "description": "Evaluate Jev/Laya System 1 + Claude System 2 stacking pattern. Returns fast-path verdict or recommends escalation with token/cost savings.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The user prompt or query to evaluate."
                },
                "criteria": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Routing categories or candidate branches."
                },
                "threshold": {
                    "type": "number",
                    "description": "Confidence threshold tau (default 0.90) required for autonomous fast-path resolution."
                }
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "laya_typed_decision",
        "description": "Evaluate arbitrary typed decision questions (choice, score, noul) against an input state in a single forward pass.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "state": {
                    "type": "string",
                    "description": "Input state (document, json, diff, or prompt)."
                },
                "questions": {
                    "type": "object",
                    "description": "Dictionary of question definitions mapping question_id to spec ({type: 'choice'|'score'|'noul', criteria: [...], instructions: '...'})."
                }
            },
            "required": ["state", "questions"]
        }
    }
]


def handle_tool_call(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    adapter = LayaAdapter(world="prod")
    deadline = clock.now() + timedelta(seconds=10)
    idem_key = f"mcp-laya-{tool_name}-{abs(hash(str(arguments)))}"

    try:
        if tool_name == "laya_status":
            health = adapter.healthz()
            env_res = adapter.execute("check_environment", {}, idem_key=idem_key, deadline=deadline)
            card_res = adapter.execute("get_model_card", {}, idem_key=idem_key + "-card", deadline=deadline)
            payload = {
                "ok": health.ok,
                "detail": health.detail,
                "latency_ms": health.latency_ms,
                "environment": env_res.data if env_res.ok else {},
                "model_card": card_res.data if card_res.ok else {},
            }
            return {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}]}

        elif tool_name == "laya_classify_intent":
            res = adapter.execute(
                "classify_intent",
                {"text": arguments.get("text", ""), "categories": arguments.get("categories", ["general"])},
                idem_key=idem_key,
                deadline=deadline,
            )
            return {"content": [{"type": "text", "text": json.dumps(res.data if res.ok else {"error": res.error}, indent=2)}]}

        elif tool_name == "laya_guardrail_check":
            res = adapter.execute(
                "guardrail_check",
                {"text": arguments.get("text", "")},
                idem_key=idem_key,
                deadline=deadline,
            )
            return {"content": [{"type": "text", "text": json.dumps(res.data if res.ok else {"error": res.error}, indent=2)}]}

        elif tool_name == "laya_score_rubric":
            res = adapter.execute(
                "score_rubric",
                {"text": arguments.get("text", ""), "rubric": arguments.get("rubric", ["poor", "acceptable", "excellent"])},
                idem_key=idem_key,
                deadline=deadline,
            )
            return {"content": [{"type": "text", "text": json.dumps(res.data if res.ok else {"error": res.error}, indent=2)}]}

        elif tool_name == "laya_stacking_evaluate":
            verdict = evaluate_stack(
                prompt=arguments.get("prompt", ""),
                criteria=arguments.get("criteria", ["billing", "technical", "general"]),
                threshold=float(arguments.get("threshold", 0.90)),
                adapter=adapter,
            )
            return {"content": [{"type": "text", "text": json.dumps(verdict.to_dict(), indent=2)}]}

        elif tool_name == "laya_typed_decision":
            res = adapter.execute(
                "typed_decision",
                {"state": arguments.get("state", ""), "questions": arguments.get("questions", {})},
                idem_key=idem_key,
                deadline=deadline,
            )
            return {"content": [{"type": "text", "text": json.dumps(res.data if res.ok else {"error": res.error}, indent=2)}]}

        else:
            return {"content": [{"type": "text", "text": f"Error: Unknown tool {tool_name}"}], "isError": True}

    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error executing {tool_name}: {str(e)}"}], "isError": True}


def run_stdio_server():
    """High-resilience JSON-RPC 2.0 stdio server."""
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip().lstrip('﻿')
        if not line:
            continue

        try:
            req = json.loads(line)
        except Exception as e:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {str(e)}"},
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()
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
                    "serverInfo": {"name": "laya-typed-decisions", "version": "1.0.0"},
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
