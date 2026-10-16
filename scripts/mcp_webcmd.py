#!/usr/bin/env python3
"""WebCMD Universal Model Context Protocol (MCP) Server.

Exposes WebCMD self-learning browser memory and 90% token-reduction DOM compression
as standard MCP tools for Antigravity IDE, Claude Code, Cursor, OpenCode, and Codex.

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

from lib import webcmd_memory
from adapters.webcmd import WebCmdAdapter

TOOLS_SPEC = [
    {
        "name": "webcmd_browse",
        "description": (
            "Browse a web page, documentation URL, or web console using the WebCMD self-learning "
            "memory layer. Reduces token consumption by up to 90% by stripping boilerplate styles/scripts "
            "and synthesizing a high-density interactive action map with [@id] element shortcuts."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The target HTTP/HTTPS URL to browse."
                },
                "profile": {
                    "type": "string",
                    "description": "Optional agent workspace / cookie jar profile name.",
                    "default": "default"
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "webcmd_get_sitemap",
        "description": "Retrieve the cached domain sitemap, navigation routes, and element shortcuts learned by WebCMD.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Target domain name (e.g., 'docs.github.com' or 'example.com')."
                }
            },
            "required": ["domain"]
        }
    },
    {
        "name": "webcmd_learn_route",
        "description": "Register or update a learned route and element shortcuts into WebCMD domain memory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full URL of the route."
                },
                "title": {
                    "type": "string",
                    "description": "Human-readable title or purpose of the page."
                },
                "shortcuts": {
                    "type": "object",
                    "description": "Key-value mapping of semantic actions to CSS selectors (e.g. {'search': '#search-box'})."
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "webcmd_status",
        "description": "Get WebCMD memory operational status, cached domain counts, and lifetime tokens saved.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "webcmd_purge_cache",
        "description": "Purge cached sitemaps and learned routes for a specific domain or all memory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Domain to purge, or empty string to purge all memory."
                }
            }
        }
    }
]


def execute_tool(name: str, args: dict[str, Any]) -> str:
    adapter = WebCmdAdapter(world="prod")

    if name == "webcmd_browse":
        url = args.get("url", "")
        profile = args.get("profile", "default")
        from datetime import timedelta
        from lib import clock
        res = adapter.execute(
            "web_browse",
            {"url": url, "profile": profile},
            idem_key=f"mcp-browse-{url}",
            idem_class="scoped",
            dry_run=False,
            deadline=clock.now() + timedelta(seconds=25),
            provenance=[{"field": "$.input", "source": "mcp", "trust": "internal"}],
        )
        if not res.ok:
            return f"Error: {res.error}"
        data = res.data
        return (
            f"=== WebCMD Page Summary ===\n"
            f"Title: {data.get('title')}\n"
            f"URL: {data.get('url')}\n"
            f"Token Savings: {int(data.get('savings_ratio', 0) * 100)}% (Raw: {data.get('raw_chars')} -> Comp: {data.get('compressed_chars')} chars)\n"
            f"Interactive Actions: {len(data.get('actions', []))} mapped targets\n\n"
            f"=== Compressed Content ===\n"
            f"{data.get('compressed_text', '')}\n"
        )

    elif name == "webcmd_get_sitemap":
        domain = args.get("domain", "")
        sm = webcmd_memory.get_domain_sitemap(domain)
        if not sm:
            return f"No sitemap found for domain '{domain}'."
        return json.dumps(sm, indent=2, ensure_ascii=False)

    elif name == "webcmd_learn_route":
        url = args.get("url", "")
        title = args.get("title", "")
        shortcuts = args.get("shortcuts", {})
        comp = webcmd_memory.compress_html(f"<html><head><title>{title}</title></head><body><h1>{title}</h1></body></html>", url=url)
        webcmd_memory.learn_route(url=url, title=title, compressed_result=comp, shortcuts=shortcuts)
        return f"Successfully learned route for {url}"

    elif name == "webcmd_status":
        sitemaps = webcmd_memory._load_sitemaps()
        domains = len(sitemaps)
        routes = sum(len(d.get("routes", {})) for d in sitemaps.values())
        return (
            f"=== WebCMD Browser Memory Status ===\n"
            f"Active: Yes\n"
            f"Cached Domains: {domains}\n"
            f"Learned Routes: {routes}\n"
            f"Storage Path: {webcmd_memory.WEBCMD_STORE_DIR}\n"
        )

    elif name == "webcmd_purge_cache":
        domain = args.get("domain") or None
        success = webcmd_memory.purge_cache(domain)
        return f"Purged cache for {'domain: ' + domain if domain else 'all domains'}: {success}"

    return f"Unknown tool: {name}"


# ------------------------------------------------------------------------------
# Stdio Server Loop
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
    server = Server("webcmd-browser")

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
                server_name="webcmd-browser",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )


def run_zero_dep_stdio():
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
                        "name": "webcmd-browser",
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
    if HAS_MCP_SDK:
        try:
            asyncio.run(run_with_sdk())
            return
        except Exception:
            pass
    run_zero_dep_stdio()


if __name__ == "__main__":
    main()
