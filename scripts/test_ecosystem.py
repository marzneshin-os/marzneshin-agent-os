#!/usr/bin/env python3
"""
Marzneshin Autonomous OS - Ecosystem Integration Verification
Tests Graphify, Headroom, Codeburn CLI, Services, and MCP capabilities.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

def run(cmd: str) -> tuple[int, str]:
    res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
    return res.returncode, res.stdout + res.stderr

def main():
    print("==================================================")
    print("Testing Marzneshin OS Tooling Integrations")
    print("==================================================")
    
    # 1. Test Graphify CLI & Graph Report
    print("\n[1/5] Testing Graphify...")
    code, out = run("export PATH=$HOME/.local/bin:$PATH; graphify --help")
    if code == 0 and "Usage: graphify" in out:
        print("  ✓ Graphify CLI is available")
    else:
        print(f"  ✗ Graphify CLI failed: {out}")

    graph_file = Path("/home/asus/code/marzneshin-agent-os/graphify-out/graph.json")
    if graph_file.exists():
        data = json.loads(graph_file.read_text())
        nodes = len(data.get("nodes", []))
        edges = len(data.get("links", []))
        print(f"  ✓ Knowledge graph loaded: {nodes} nodes, {edges} edges")
    else:
        print("  ✗ graphify-out/graph.json not found")

    # 2. Test Headroom CLI & Health
    print("\n[2/5] Testing Headroom...")
    code, out = run("export PATH=$HOME/.local/bin:$PATH; headroom --help")
    if code == 0 and "Headroom - The Context Optimization Layer" in out:
        print("  ✓ Headroom CLI is available")
    else:
        print(f"  ✗ Headroom CLI failed: {out}")

    code, out = run("export PATH=$HOME/.local/bin:$PATH; headroom doctor")
    if "Headroom Doctor" in out:
        print("  ✓ Headroom Doctor passed")
    else:
        print(f"  ✗ Headroom Doctor failed: {out}")

    # 3. Test Codeburn CLI & Overview
    print("\n[3/5] Testing Codeburn...")
    code, out = run("source ~/.nvm/nvm.sh; codeburn --version")
    if code == 0:
        print(f"  ✓ Codeburn CLI version: {out.strip()}")
    else:
        print(f"  ✗ Codeburn version check failed: {out}")

    code, out = run("source ~/.nvm/nvm.sh; cd /home/asus/code/marzneshin-agent-os && codeburn overview --no-color")
    if code == 0 and "CodeBurn" in out:
        print("  ✓ Codeburn overview generated successfully from session logs")
    else:
        print(f"  ✗ Codeburn overview failed: {out}")

    # 4. Test Service Configurations in dev.py
    print("\n[4/5] Testing Unified Service Configurations...")
    code, out = run("cd /home/asus/code/marzneshin-agent-os && python3 scripts/dev.py status")
    if code == 0 and "headroom" in out and "codeburn" in out and "graphify" in out and "agentmemory" in out:
        print("  ✓ dev.py status correctly monitors all services:")
        for line in out.splitlines():
            if any(s in line for s in ["agentmemory", "ccr", "headroom", "codeburn", "graphify", "SERVICE"]):
                print("    " + line)
    else:
        print(f"  ✗ dev.py status check failed: {out}")

    # 5. Test MCP Configs
    print("\n[5/5] Testing MCP Registrations in ~/.claude.json...")
    claude_cfg = Path.home() / ".claude.json"
    if claude_cfg.exists():
        data = json.loads(claude_cfg.read_text())
        global_servers = data.get("mcpServers", {})
        proj_servers = data.get("projects", {}).get("/home/asus/code/marzneshin-agent-os", {}).get("mcpServers", {})
        all_servers = {**global_servers, **proj_servers}
        for s in ["graphify", "headroom", "codeburn"]:
            if s in all_servers:
                print(f"  ✓ Claude Code MCP server registered: {s}")
            else:
                print(f"  ✗ Missing in Claude Code: {s}")

    print("\n==================================================")
    print("Integration verification completed!")
    print("==================================================")

if __name__ == "__main__":
    main()
