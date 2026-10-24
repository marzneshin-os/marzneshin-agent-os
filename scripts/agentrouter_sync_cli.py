#!/usr/bin/env python3
"""Multi-Harness Config Synchronization CLI for AgentRouter (ADR-033).

Renders and syncs unified model mesh configurations across 10 coding agent harnesses:
claude-code, codex, opencode, ccr, antigravity, qwen, hermes, openclaw, pi, roo-cline.
Runs on pure Python 3 standard library.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

HARNESS_TARGETS = [
    "antigravity",
    "claude-code",
    "codex",
    "opencode",
    "ccr",
    "qwen",
    "hermes",
    "openclaw",
    "pi",
    "roo-cline",
]

DEFAULT_MODELS = [
    "gpt-6.1sol",
    "gpt-6-astra",
    "claude-opus-5",
    "claude-opus-4-8",
    "gpt-5.6-sol",
    "glm-5.3",
    "deepseek-v4-flash",
]


def get_base_url(use_local_gateway: bool = True, for_anthropic: bool = False) -> str:
    """Return appropriate base URL based on protocol and gateway preference."""
    if use_local_gateway:
        return "http://127.0.0.1:8787" if for_anthropic else "http://127.0.0.1:8787/v1"
    raw = os.environ.get("AGENTROUTER_BASE_URL", "https://agentrouter.org/v1").rstrip("/")
    if for_anthropic and raw.endswith("/v1"):
        return raw[:-3]
    return raw


def render_config(target: str, use_local_gateway: bool = True) -> str:
    """Render ready-to-use configuration content for the specified harness."""
    target_norm = target.lower().strip()
    placeholder_key = "<AGENTROUTER_API_KEY>"

    if target_norm == "claude-code":
        anth_base = get_base_url(use_local_gateway, for_anthropic=True)
        config = {
            "env": {
                "ANTHROPIC_BASE_URL": anth_base,
                "ANTHROPIC_MODEL": "claude-opus-5",
                "ANTHROPIC_DEFAULT_SONNET_MODEL": "gpt-6.1sol",
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": "deepseek-v4-flash",
                "ANTHROPIC_API_KEY": placeholder_key,
            },
            "description": "Claude Code environment configuration for AgentRouter mesh",
        }
        return json.dumps(config, indent=2)

    if target_norm == "codex":
        oai_base = get_base_url(use_local_gateway, for_anthropic=False)
        models_str = ",\n  ".join(f'"{m}"' for m in DEFAULT_MODELS)
        return f"""# Codex CLI AgentRouter Configuration (ADR-033)
model = "gpt-6.1sol"
model_provider = "AgentRouter"

[model_providers.AgentRouter]
base_url = "{oai_base}"
wire_api = "responses"
models = [
  {models_str}
]

[mcp_servers.agentmemory]
command = "npx"
args = ["-y", "agentmemory", "mcp"]
"""

    if target_norm == "opencode":
        oai_base = get_base_url(use_local_gateway, for_anthropic=False)
        anth_base = get_base_url(use_local_gateway, for_anthropic=True)
        config = {
            "$schema": "https://opencode.dev/schema.json",
            "provider": "AgentRouter-openai-gateway",
            "model": "AgentRouter-openai-gateway/gpt-6.1sol",
            "providers": {
                "AgentRouter-openai-gateway": {
                    "type": "@ai-sdk/openai-compatible",
                    "baseURL": oai_base,
                    "apiKey": placeholder_key,
                },
                "AgentRouter-anthropic-gateway": {
                    "type": "@ai-sdk/anthropic",
                    "baseURL": anth_base,
                    "apiKey": placeholder_key,
                },
            },
            "mcp": {
                "agentmemory": {
                    "command": "npx",
                    "args": ["-y", "agentmemory", "mcp"],
                }
            },
        }
        return json.dumps(config, indent=2)

    if target_norm == "ccr":
        oai_base = get_base_url(use_local_gateway, for_anthropic=False)
        config = {
            "Providers": [
                {
                    "name": "agentrouter",
                    "api_base": f"{oai_base}/chat/completions",
                    "api_key": placeholder_key,
                    "models": DEFAULT_MODELS,
                }
            ],
            "Router": {
                "default": "agentrouter,gpt-6.1sol",
                "think": "agentrouter,claude-opus-5",
                "background": "agentrouter,deepseek-v4-flash",
                "longContext": "agentrouter,gpt-6.1sol",
            },
        }
        return json.dumps(config, indent=2)

    if target_norm == "antigravity":
        oai_base = get_base_url(use_local_gateway, for_anthropic=False)
        config = {
            "model_provider": "AgentRouter",
            "base_url": oai_base,
            "default_model": "gpt-6.1sol",
            "apex_model": "gpt-6-astra",
            "reasoning_model": "claude-opus-5",
            "mcp_servers": {
                "agentrouter-mesh": {
                    "command": "python3",
                    "args": ["scripts/mcp_agentrouter.py"],
                }
            },
        }
        return json.dumps(config, indent=2)

    if target_norm == "qwen":
        oai_base = get_base_url(use_local_gateway, for_anthropic=False)
        config = {
            "openai_base_url": oai_base,
            "openai_api_key": placeholder_key,
            "model": "gpt-6.1sol",
            "fallback_model": "deepseek-v4-flash",
        }
        return json.dumps(config, indent=2)

    if target_norm == "hermes":
        oai_base = get_base_url(use_local_gateway, for_anthropic=False)
        config = {
            "base_url": oai_base,
            "api_key": placeholder_key,
            "model": "gpt-6.1sol",
            "provider": "agentrouter",
        }
        return json.dumps(config, indent=2)

    if target_norm == "openclaw":
        oai_base = get_base_url(use_local_gateway, for_anthropic=False)
        config = {
            "base_url": oai_base,
            "api_key": placeholder_key,
            "model": "gpt-6.1sol",
            "temperature": 0.2,
        }
        return json.dumps(config, indent=2)

    if target_norm == "pi":
        oai_base = get_base_url(use_local_gateway, for_anthropic=False)
        config = {
            "base_url": oai_base,
            "api_key": placeholder_key,
            "default_model": "gpt-6.1sol",
        }
        return json.dumps(config, indent=2)

    if target_norm == "roo-cline":
        oai_base = get_base_url(use_local_gateway, for_anthropic=False)
        config = {
            "api_provider": "openai-compatible",
            "api_base": oai_base,
            "api_key": placeholder_key,
            "model_id": "gpt-6.1sol",
        }
        return json.dumps(config, indent=2)

    raise ValueError(f"Unknown harness target: '{target}'. Supported targets: {', '.join(HARNESS_TARGETS)}")


def get_default_config_path(target: str) -> Path:
    """Return the canonical target config path in workspace."""
    target_norm = target.lower().strip()
    if target_norm == "claude-code":
        return WORKSPACE_ROOT / ".claude" / "agentrouter.env.json"
    if target_norm == "codex":
        return WORKSPACE_ROOT / ".codex" / "config.toml"
    if target_norm == "opencode":
        return WORKSPACE_ROOT / "opencode.json"
    if target_norm == "ccr":
        return WORKSPACE_ROOT / ".ccr" / "config.json"
    if target_norm == "antigravity":
        return WORKSPACE_ROOT / ".gemini" / "agentrouter.json"
    return WORKSPACE_ROOT / f".{target_norm}" / "config.json"


def sync_target(
    target: str,
    dry_run: bool = False,
    use_local_gateway: bool = True,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Sync rendered configuration to filesystem with backup protection."""
    content = render_config(target, use_local_gateway)
    dest_path = Path(output_dir) / f"{target}.json" if output_dir else get_default_config_path(target)

    result = {
        "target": target,
        "destination": str(dest_path),
        "dry_run": dry_run,
        "backed_up": False,
        "status": "pending",
    }

    if dry_run:
        result["status"] = "dry_run_passed"
        result["content_preview"] = content[:150] + "..." if len(content) > 150 else content
        return result

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if dest_path.exists():
        backup_path = dest_path.with_suffix(dest_path.suffix + ".bak")
        shutil.copy2(dest_path, backup_path)
        result["backed_up"] = True
        result["backup_path"] = str(backup_path)

    dest_path.write_text(content, encoding="utf-8")
    result["status"] = "synced"
    return result


def cli_status() -> None:
    """Report status and config wiring paths across all harnesses."""
    print("=" * 60)
    print("  AgentRouter Multi-Harness Sync Status (ADR-033)")
    print("=" * 60)
    for target in HARNESS_TARGETS:
        dest = get_default_config_path(target)
        status_icon = "✅ EXISTS" if dest.exists() else "⬜ NOT_CONFIGURED"
        print(f"  [{target:<12}] {status_icon} -> {dest}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentRouter Multi-Harness Config Sync CLI (ADR-033)")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status", help="Show harness config wiring status")

    render_parser = subparsers.add_parser("render", help="Render configuration for target harness")
    render_parser.add_argument("target", choices=HARNESS_TARGETS + ["all"], help="Target harness")
    render_parser.add_argument("--use-local-gateway", action="store_true", default=True, help="Use 127.0.0.1:8787")

    sync_parser = subparsers.add_parser("sync", help="Synchronize configs to target harness files")
    sync_parser.add_argument("--target", default="all", choices=HARNESS_TARGETS + ["all"], help="Target harness or all")
    sync_parser.add_argument("--dry-run", action="store_true", default=False, help="Dry run without writing files")
    sync_parser.add_argument("--use-local-gateway", action="store_true", default=True, help="Use 127.0.0.1:8787")
    sync_parser.add_argument("--output-dir", type=str, default=None, help="Custom output directory")

    args = parser.parse_args()

    if args.command == "status":
        cli_status()
    elif args.command == "render":
        if args.target == "all":
            for t in HARNESS_TARGETS:
                print(f"--- Harness: {t} ---")
                print(render_config(t, args.use_local_gateway))
                print()
        else:
            print(render_config(args.target, args.use_local_gateway))
    elif args.command == "sync":
        targets = HARNESS_TARGETS if args.target == "all" else [args.target]
        results = [
            sync_target(t, dry_run=args.dry_run, use_local_gateway=args.use_local_gateway, output_dir=args.output_dir)
            for t in targets
        ]
        print(json.dumps(results, indent=2))
    else:
        cli_status()


if __name__ == "__main__":
    main()
