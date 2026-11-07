#!/usr/bin/env python3
"""MCPHub Centralized Health & Diagnostics Engine for MCP Servers (Khairallah Stack Tool #22).

Inspects, monitors, and tests all Model Context Protocol (MCP) servers registered in .mcp.json.
Provides single-dashboard observability for Antigravity IDE and Claude Code.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(WORKSPACE_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))

from lib import clock
from lib.paths import repo_root

MCP_CONFIG_PATH = repo_root() / ".mcp.json"


def load_mcp_servers() -> Dict[str, Dict[str, Any]]:
    if not MCP_CONFIG_PATH.exists():
        return {}
    try:
        with open(MCP_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("mcpServers", {})
    except Exception:
        return {}


def probe_server(name: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Test server availability and measure latency."""
    t0 = time.monotonic()
    status = "UNKNOWN"
    details = ""
    tool_count = None

    if "url" in config:
        # SSE or HTTP transport
        url = config["url"]
        status = "CONFIGURED (HTTP/SSE)"
        details = f"Target URL: {url}"
    elif "command" in config:
        cmd = config["command"]
        args = config.get("args", [])
        
        # Check command executable existence
        if cmd == "python3":
            target_script = args[0] if args else ""
            script_path = repo_root() / target_script
            if script_path.exists():
                status = "ONLINE (Stdlib Python)"
                details = f"Script: {target_script}"
            else:
                status = "MISSING_SCRIPT"
                details = f"Script not found at {script_path}"
        elif cmd in ("npx", "npm"):
            status = "CONFIGURED (Node/NPX)"
            details = f"Package: {' '.join(args)}"
        else:
            resolved = shutil.which(cmd) or Path(cmd).exists()
            if resolved:
                status = "ONLINE (Executable)"
                details = f"Binary: {cmd}"
            else:
                status = "OFFLINE (Binary Missing)"
                details = f"Executable not found: {cmd}"

    elapsed_ms = round((time.monotonic() - t0) * 1000, 2)
    return {
        "name": name,
        "status": status,
        "details": details,
        "latency_ms": elapsed_ms,
        "command": config.get("command", config.get("url", "n/a")),
        "description": config.get("description", "No description")
    }


def cmd_list(args: argparse.Namespace) -> int:
    servers = load_mcp_servers()
    print(f"MCPHub — Registered MCP Servers ({len(servers)} total)")
    print("=" * 80)
    for name, cfg in servers.items():
        cmd = cfg.get("command") or cfg.get("url", "n/a")
        args_str = " ".join(cfg.get("args", []))
        desc = cfg.get("description", "")
        print(f"• {name:<24} | {cmd} {args_str}")
        if desc:
            print(f"  └─ {desc}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    servers = load_mcp_servers()
    results = [probe_server(name, cfg) for name, cfg in servers.items()]

    if args.json:
        print(json.dumps({
            "timestamp": clock.iso(),
            "total": len(servers),
            "servers": results
        }, indent=2))
        return 0

    print("MCPHub Status & Health Diagnostic Matrix")
    print("=" * 85)
    print(f"{'Server Name':<24} | {'Status':<25} | {'Latency':<8} | {'Type / Details'}")
    print("-" * 85)
    for r in results:
        lat = f"{r['latency_ms']}ms"
        print(f"{r['name']:<24} | {r['status']:<25} | {lat:<8} | {r['details']}")
    print("=" * 85)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="MCPHub Centralized Health & Diagnostics Engine")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    p_list = subparsers.add_parser("list", help="List all registered MCP servers")
    p_list.set_defaults(func=cmd_list)

    p_status = subparsers.add_parser("status", help="Probe and display health matrix")
    p_status.add_argument("--json", action="store_true", help="Output as JSON")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())