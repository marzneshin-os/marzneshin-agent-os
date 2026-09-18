#!/usr/bin/env python3
"""router.py — CLI for OmniRoute / Claude Code Router (CCR) Gateway operations."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

from adapters.omniroute import OmniRouteAdapter, CCRAdapter, _build_url
from adapters.base import IdemClass, deadline_remaining_s
from lib import router, tokensaver, ids, clock


def cmd_doctor(args: argparse.Namespace) -> int:
    config = router.load_config()
    gateways = config.get("gateways", {})
    
    print("LLM Gateway Doctor (Claude Code Router & OmniRoute)")
    print("=" * 55)
    
    overall_ok = False
    for gw_name, gw_cfg in gateways.items():
        if not gw_cfg.get("enabled", True):
            continue
        adapter = OmniRouteAdapter(gateway_name=gw_name)
        health = adapter.healthz()
        status_str = "\033[32mOK\033[0m" if health.ok else "\033[31mDOWN\033[0m"
        print(f"Gateway [{gw_name}]: {status_str} ({health.detail}) [{health.latency_ms:.1f}ms]")
        if health.ok:
            overall_ok = True
            
    print("-" * 55)
    print("Combos configured:  ", list(config.get("combos", {}).keys()))
    print("Default Combo:      ", config.get("routing", {}).get("default_combo", "fable-planner"))
    print("Prefer CCR:         ", config.get("routing", {}).get("prefer_ccr", False))
    print("Quota configured:   ", config.get("quota", {}))
    print("=" * 55)
    return 0 if overall_ok else 1


def cmd_models(args: argparse.Namespace) -> int:
    config = router.load_config()
    
    print("Configured Gateway / Combo Models:")
    print("-" * 45)
    combos = config.get("combos", {})
    for name, models in combos.items():
        print(f"Combo '{name}':")
        for m in models:
            print(f"  - {m}")
            
    # Try fetching live models from active gateway
    adapter = OmniRouteAdapter()
    health = adapter.healthz()
    if health.ok:
        gw_name, gw_cfg = adapter._resolve_gateway(config)
        base_url = gw_cfg.get("base_url", "")
        api_key = gw_cfg.get("api_key", "")
        try:
            url = _build_url(base_url, "v1/models")
            req = urllib.request.Request(url)
            if api_key:
                req.add_header("Authorization", f"Bearer {api_key}")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models_list = data.get("data", [])
                print(f"\nLive Upstream Models (via active gateway '{gw_name}', {len(models_list)} available):")
                print("-" * 45)
                for m in models_list:
                    mid = m.get("id", "")
                    mname = m.get("display_name", "")
                    owner = m.get("owned_by", "")
                    suffix = f" -> {mname}" if mname and mname != mid else ""
                    print(f"  [{owner}] {mid}{suffix}")
        except Exception as e:
            print(f"\nNote: Could not query live models: {e}")
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    gateway_name = args.gateway
    adapter = OmniRouteAdapter(gateway_name=gateway_name)
    
    messages = [{"role": "user", "content": args.message}]
    payload = {
        "model": args.model or "antigravity",
        "messages": messages,
        "rtk_enabled": not args.no_rtk,
        "caveman_level": args.caveman,
        "ponytail_enabled": args.ponytail
    }

    op = "llm_chat"
    if getattr(args, "reasoning", None):
        payload["reasoning_effort"] = args.reasoning
        op = "llm_reason"
    if getattr(args, "thinking", False):
        payload["thinking"] = True
        op = "llm_think"
    if getattr(args, "deep_search", False):
        payload["deep_search"] = True
        op = "llm_search"
    
    deadline = clock.now()
    import datetime as dt
    deadline = deadline + dt.timedelta(minutes=5)
    
    try:
        idem_key = ids.new_ulid()
        res = adapter.execute(
            op,
            payload,
            idem_key=idem_key,
            idem_class="none",
            dry_run=False,
            deadline=deadline,
            provenance=[]
        )
        if res.ok:
            data = res.data
            choices = data.get("choices", [])
            choice = choices[0].get("message", {}).get("content", "") if choices else ""
            print(choice)
            if args.verbose:
                print("\n" + "-" * 30)
                print("Usage:  ", data.get("usage", {}))
                print("Latency:", f"{res.duration_ms:.2f}ms")
                usage_file = router.router_usage_file()
                if usage_file.exists():
                    with open(usage_file) as f:
                        lines = f.read().splitlines()
                        if lines:
                            last = json.loads(lines[-1])
                            print("Model:  ", last.get("model"))
            return 0
        else:
            print(f"Request failed: {res.error}", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_usage(args: argparse.Namespace) -> int:
    usage_file = router.router_usage_file()
    if not usage_file.exists():
        print("No usage data found.")
        return 0
        
    print(f"Usage records (from {usage_file}):")
    print("-" * 50)
    with open(usage_file) as f:
        for line in f:
            if line.strip():
                try:
                    record = json.loads(line)
                    date = record.get("date", record.get("ts", "")[:10])
                    model = record.get("model", "")
                    tokens = record.get("tokens", 0)
                    print(f"[{date}] Model: {model:<30} Tokens: {tokens:<8}")
                except json.JSONDecodeError:
                    pass
    return 0


def cmd_quota(args: argparse.Namespace) -> int:
    today = clock.now().date().isoformat()
    used = router.get_daily_usage(today)
    config = router.load_config()
    quota = config.get("quota", {})
    max_tokens = quota.get("max_tokens_per_call", 128000)
    max_usd = quota.get("max_daily_usd", 0.0)
    alert_usd = quota.get("alert_threshold_usd", 0.0)

    print("Quota & Usage Status")
    print("-" * 30)
    print(f"Date:                {today}")
    print(f"Tokens Used Today:   {used}")
    print(f"Max Tokens/Call:     {max_tokens}")
    print(f"Max Daily USD:       ${max_usd:.2f}")
    print(f"Alert Threshold USD: ${alert_usd:.2f}")
    print("-" * 30)
    if used > 0:
        print("Status: Active")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LLM Gateway CLI (CCR / OmniRoute)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="Check gateway health and config")
    
    models = subparsers.add_parser("models", help="List available models and combos")
    
    chat = subparsers.add_parser("chat", help="Send a chat message via the gateway")
    chat.add_argument("message", help="The message to send")
    chat.add_argument("--model", help="Specific model or combo name to use")
    chat.add_argument("--gateway", help="Specific gateway name to route through (e.g. ccr, omniroute)")
    chat.add_argument("--no-rtk", action="store_true", help="Disable Request/Token filters")
    chat.add_argument("--caveman", type=int, choices=[1, 2, 3], help="Caveman mode level")
    chat.add_argument("--ponytail", action="store_true", help="Enable ponytail strict mode")
    chat.add_argument("--reasoning", choices=["none", "minimal", "low", "medium", "high", "xhigh", "max"], help="Reasoning effort level")
    chat.add_argument("--thinking", action="store_true", help="Enable thinking mode (FreeModels, Anthropic, Qwen)")
    chat.add_argument("--deep-search", action="store_true", help="Enable deep search capability (FreeModels, Perplexity)")
    chat.add_argument("-v", "--verbose", action="store_true", help="Show usage and latency")
    
    usage = subparsers.add_parser("usage", help="Show usage records")
    
    quota = subparsers.add_parser("quota", help="Show quota status")

    args = parser.parse_args(argv)

    if args.command == "doctor":
        return cmd_doctor(args)
    elif args.command == "models":
        return cmd_models(args)
    elif args.command == "chat":
        return cmd_chat(args)
    elif args.command == "usage":
        return cmd_usage(args)
    elif args.command == "quota":
        return cmd_quota(args)

    return 1


if __name__ == "__main__":
    sys.exit(main())
