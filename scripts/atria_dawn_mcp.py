#!/usr/bin/env python3
"""
Atria-Dawn Universal MCP Server
Exposes Shanghai AI Lab's 744B MoE Atria-Dawn-Preview model as an MCP toolset
for Antigravity IDE, Claude Code, and agentic workflows.

Architecture:
- Native MCP SDK integration if available (mcp.server).
- High-resilience Zero-Dependency JSON-RPC 2.0 fallback if running in environments
  without external packages installed.
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Any, Optional

# Auto-locate workspace root and load .env.atria if available
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

def load_atria_env() -> str:
    key = os.getenv("ATRIA_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")
    if key:
        return key.strip()
    
    env_file = WORKSPACE_ROOT / ".env.atria"
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k in ("ATRIA_API_KEY", "ANTHROPIC_AUTH_TOKEN") and v:
                        return v
    return ""

ATRIA_BASE_URL = os.getenv("ATRIA_BASE_URL", "https://api.atria-asi.ai/v1")
MODEL_NAME = os.getenv("ATRIA_MODEL", "Atria-Dawn-Preview")

TOOLS_SPEC = [
    {
        "name": "atria_reason",
        "description": (
            "Execute deep agentic, architectural, or algorithmic reasoning with the "
            "744B parameter Atria-Dawn-Preview MoE foundation model (leveraging free 100M tokens)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The complex engineering, math, architecture, or code problem to solve."
                },
                "system_instruction": {
                    "type": "string",
                    "description": "Optional system prompt defining behavior, constraints, or architecture guidelines.",
                    "default": "You are Atria-Dawn, a 744B MoE agentic engineering intelligence."
                },
                "temperature": {
                    "type": "number",
                    "description": "Sampling temperature (default: 0.2 for deterministic coding).",
                    "default": 0.2
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Maximum tokens to generate (default: 4096).",
                    "default": 4096
                }
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "atria_generate_code",
        "description": "Generate production-grade code, modules, tests, or documentation with Atria-Dawn-Preview.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_description": {
                    "type": "string",
                    "description": "Detailed description of the code or module to generate."
                },
                "language": {
                    "type": "string",
                    "description": "Target language (e.g. python, typescript, bash, go).",
                    "default": "python"
                },
                "existing_context": {
                    "type": "string",
                    "description": "Optional existing code, interfaces, or type definitions to build upon."
                }
            },
            "required": ["task_description"]
        }
    },
    {
        "name": "atria_debug_code",
        "description": "Analyze failing code, logs, and stack traces to produce root-cause diagnoses and surgical fixes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The buggy or failing code block."
                },
                "error_trace": {
                    "type": "string",
                    "description": "Error output, exception traceback, or test failure message."
                },
                "expected_behavior": {
                    "type": "string",
                    "description": "Description of what the code is supposed to do."
                }
            },
            "required": ["code", "error_trace"]
        }
    },
    {
        "name": "atria_health",
        "description": "Verify Atria API connectivity, authentication status, and token latency.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]


def sync_call_atria(messages: list[dict[str, str]], temperature: float = 0.2, max_tokens: int = 4096) -> str:
    import urllib.request
    import urllib.error

    key = load_atria_env()
    if not key:
        return (
            "Error: ATRIA_API_KEY is not configured.\n"
            "Please add your API key to .env.atria in the project root:\n"
            "ATRIA_API_KEY=\"your_key_here\"\n"
            "Get 100M free tokens at https://api.atria-asi.ai"
        )

    url = f"{ATRIA_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            msg = data["choices"][0]["message"]
            content = msg.get("content") or ""
            reasoning = msg.get("reasoning_content") or ""
            if content and reasoning:
                return f"{content}\n\n---\n**Atria 744B Thinking Trace:**\n{reasoning}"
            return content or reasoning or "No text generated."
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return "Authentication Failed (HTTP 401): The provided ATRIA_API_KEY is invalid or expired. Check https://api.atria-asi.ai"
        elif e.code == 429:
            return "Rate Limit Exceeded (HTTP 429): Atria API rate limit reached. Please retry in a few moments."
        else:
            err_msg = e.read().decode("utf-8", errors="ignore")
            return f"Atria API Error (HTTP {e.code}): {err_msg}"
    except Exception as e:
        return f"Error communicating with Atria API: {str(e)}"


def execute_tool(name: str, args: dict[str, Any]) -> str:
    if name == "atria_health":
        key = load_atria_env()
        if not key:
            return "❌ ATRIA_API_KEY is missing. Configure it in .env.atria"

        import urllib.request
        import time

        url = f"{ATRIA_BASE_URL.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 40
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers)

        t0 = time.time()  # clock-ok: live network latency probe
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                elapsed = round((time.time() - t0) * 1000, 2)  # clock-ok
                return f"✅ Atria-Dawn 744B MoE is ONLINE & AUTHENTICATED!\n⚡ Latency: {elapsed}ms\n🎯 Model: {MODEL_NAME}\n🌐 Gateway: {ATRIA_BASE_URL}\n🎉 100M Free Token Pool: ACTIVE"
        except Exception as e:
            return f"❌ Failed to reach Atria API: {str(e)}"

    elif name == "atria_reason":
        prompt = args.get("prompt", "")
        system_instruction = args.get("system_instruction") or "You are Atria-Dawn, a 744B MoE agentic engineering intelligence."
        temperature = float(args.get("temperature", 0.2))
        max_tokens = int(args.get("max_tokens", 4096))

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ]
        return sync_call_atria(messages, temperature=temperature, max_tokens=max_tokens)

    elif name == "atria_generate_code":
        task = args.get("task_description", "")
        lang = args.get("language", "python")
        ctx = args.get("existing_context", "")

        prompt = f"Target Language: {lang}\n\nTask:\n{task}"
        if ctx:
            prompt += f"\n\nExisting Context / Interfaces:\n{ctx}"

        messages = [
            {
                "role": "system",
                "content": (
                    "You are Atria-Dawn, an expert senior software architect. "
                    "Write clean, robust, production-ready code with no unnecessary fluff. "
                    "Include type annotations and defensive error handling."
                )
            },
            {"role": "user", "content": prompt}
        ]
        return sync_call_atria(messages, temperature=0.1, max_tokens=4096)

    elif name == "atria_debug_code":
        code = args.get("code", "")
        trace = args.get("error_trace", "")
        expected = args.get("expected_behavior", "")

        prompt = f"Code snippet:\n```\n{code}\n```\n\nError / Traceback:\n```\n{trace}\n```"
        if expected:
            prompt += f"\n\nExpected Behavior:\n{expected}"

        messages = [
            {
                "role": "system",
                "content": (
                    "You are Atria-Dawn, an elite debugging specialist. "
                    "Diagnose the exact root cause of the error, explain it concisely, "
                    "and provide the surgical fix."
                )
            },
            {"role": "user", "content": prompt}
        ]
        return sync_call_atria(messages, temperature=0.1, max_tokens=4096)

    else:
        return f"Unknown tool: {name}"


# ------------------------------------------------------------------------------
# Server Runner
# ------------------------------------------------------------------------------
try:
    from mcp.server import Server, NotificationOptions
    from mcp.server.models import InitializationOptions
    from mcp.server.stdio import stdio_server
    import mcp.types as types
    HAS_MCP_SDK = True
except ImportError:
    HAS_MCP_SDK = False


async def run_with_sdk():
    server = Server("atria-dawn")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"]
            )
            for t in TOOLS_SPEC
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.TextContent]:
        res_text = execute_tool(name, arguments or {})
        return [types.TextContent(type="text", text=res_text)]

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="atria-dawn",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )


def run_zero_dep_stdio():
    """Universal JSON-RPC 2.0 Stdio loop with zero external dependencies."""
    while True:
        line = sys.stdin.readline()
        if not line:
            break
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
                        "name": "atria-dawn",
                        "version": "1.0.0"
                    }
                }
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "notifications/initialized":
            pass

        elif method == "ping":
            resp = {"jsonrpc": "2.0", "id": req_id, "result": {}}
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

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
            name = params.get("name", "")
            args = params.get("arguments", {})
            text_result = execute_tool(name, args)
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": text_result}],
                    "isError": False
                }
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


def main():
    if HAS_MCP_SDK:
        asyncio.run(run_with_sdk())
    else:
        run_zero_dep_stdio()


if __name__ == "__main__":
    main()
