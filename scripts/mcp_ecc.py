#!/usr/bin/env python3
"""ECC Universal Model Context Protocol (MCP) Server.

Exposes Everything Claude Code (ECC) Universal Agent Harness capabilities:
- AgentShield security audits (secret detection, prompt injection defense, unsafe commands).
- Continuous Learning Instincts (learn, query, confidence tracking).
- Cross-agentic harness parity audit across Antigravity, Claude Code, Cursor, OpenCode, and others.

Architecture:
- Native MCP SDK integration if available (mcp.server).
- High-resilience Zero-Dependency JSON-RPC 2.0 stdio engine for stdlib-only environments.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(WORKSPACE_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))

from lib.ecc_harness import AgentShieldScanner, HarnessAudit, InstinctStore

TOOLS_SPEC = [
    {
        "name": "ecc_agentshield_scan",
        "description": (
            "Run an AgentShield security audit across workspace files, configurations, rules, or prompts. "
            "Detects exposed secrets, prompt injection directives, and dangerous command executions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "targets": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of file paths relative to repo root to scan."
                },
                "strict": {
                    "type": "boolean",
                    "description": "Whether to fail on MEDIUM severity findings in addition to CRITICAL and HIGH.",
                    "default": False
                }
            }
        }
    },
    {
        "name": "ecc_instinct_query",
        "description": "Query the continuous learning instincts catalog for project conventions, architectural rules, or bug-fix lessons.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keywords or file path pattern to match against triggers or actions."
                },
                "domain": {
                    "type": "string",
                    "description": "Optional domain filter (e.g. 'security', 'python', 'architecture', 'testing')."
                }
            }
        }
    },
    {
        "name": "ecc_instinct_learn",
        "description": "Store a new learned pattern, architectural invariant, or bug-fix lesson into persistent instincts memory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "trigger": {
                    "type": "string",
                    "description": "Regex or keyword triggering this instinct (e.g. file pattern or task context)."
                },
                "action": {
                    "type": "string",
                    "description": "The specific rule, convention, or recommended action to apply."
                },
                "rationale": {
                    "type": "string",
                    "description": "Why this rule exists."
                },
                "domain": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Category tags for grouping."
                },
                "confidence": {
                    "type": "number",
                    "description": "Initial confidence score between 0.1 and 1.0.",
                    "default": 0.8
                }
            },
            "required": ["trigger", "action"]
        }
    },
    {
        "name": "ecc_harness_audit",
        "description": "Audit configuration and rule alignment across all coding agent harnesses (Antigravity, Claude Code, Cursor, Cline, Windsurf, Kilo).",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]

def execute_tool(name: str, args: dict[str, Any]) -> str:
    if name == "ecc_agentshield_scan":
        scanner = AgentShieldScanner(repo_root=WORKSPACE_ROOT)
        targets = args.get("targets")
        strict = args.get("strict", False)
        report = scanner.scan_workspace(targets=targets, strict=strict)
        return json.dumps(report.to_dict(), indent=2)

    elif name == "ecc_instinct_query":
        store = InstinctStore(repo_root=WORKSPACE_ROOT)
        results = store.query(
            query_str=args.get("query"),
            domain=args.get("domain"),
        )
        return json.dumps([r.to_dict() for r in results], indent=2)

    elif name == "ecc_instinct_learn":
        store = InstinctStore(repo_root=WORKSPACE_ROOT)
        inst = store.learn(
            trigger=args["trigger"],
            action=args["action"],
            rationale=args.get("rationale", ""),
            domain=args.get("domain"),
            confidence=float(args.get("confidence", 0.8)),
            provenance="mcp_tool_call",
        )
        return json.dumps(inst.to_dict(), indent=2)

    elif name == "ecc_harness_audit":
        auditor = HarnessAudit(repo_root=WORKSPACE_ROOT)
        report = auditor.audit()
        return json.dumps(report.to_dict(), indent=2)

    raise ValueError(f"Unknown MCP tool: {name}")


def run_zero_dep_stdio() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue

        method = req.get("method")
        req_id = req.get("id")

        if method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "experimental": {},
                        "tools": {"listChanged": False}
                    },
                    "serverInfo": {
                        "name": "ecc-harness",
                        "version": "1.0.0"
                    }
                }
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "notifications/initialized":
            pass

        elif method == "tools/list":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": TOOLS_SPEC
                }
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "tools/call":
            params = req.get("params", {})
            tool_name = params.get("name", "")
            args = params.get("arguments", {})
            try:
                res_text = execute_tool(tool_name, args)
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": res_text}
                        ]
                    }
                }
            except Exception as e:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": f"Error: {str(e)}"}
                        ],
                        "isError": True
                    }
                }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif req_id is not None:
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method '{method}' not found"
                }
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


def main():
    run_zero_dep_stdio()


if __name__ == "__main__":
    main()
