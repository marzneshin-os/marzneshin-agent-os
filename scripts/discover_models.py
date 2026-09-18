#!/usr/bin/env python3
"""discover_models.py — Auto-discover available models from all configured gateways.

Usage:
  python3 scripts/discover_models.py --all        # Discover from all gateways
  python3 scripts/discover_models.py --free        # Show only free models
  python3 scripts/discover_models.py --reasoning   # Show models with reasoning capability
  python3 scripts/discover_models.py --thinking    # Show models with thinking/deep-search
  python3 scripts/discover_models.py --gateway xkiro  # Discover from specific gateway
  python3 scripts/discover_models.py --summary     # Compact summary table
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

from lib import router


FREEMODELS_CATALOG = [
    {
        "id": "claude-fable-5.1",
        "display_name": "Claude Fable 5.1",
        "owned_by": "anthropic",
        "access_tier": "free",
        "capabilities": {"vision": True, "tools": True, "reasoning": True, "thinking": True, "deep_search": True},
        "context_length": 200000,
    },
    {
        "id": "claude-fable-5",
        "display_name": "Claude Fable 5",
        "owned_by": "anthropic",
        "access_tier": "free",
        "capabilities": {"vision": True, "tools": True, "reasoning": True, "thinking": True, "deep_search": True},
        "context_length": 200000,
    },
    {
        "id": "claude-sonnet-5",
        "display_name": "Claude Sonnet 5",
        "owned_by": "anthropic",
        "access_tier": "free",
        "capabilities": {"vision": True, "tools": True, "reasoning": True, "thinking": True, "deep_search": True},
        "context_length": 200000,
    },
    {
        "id": "gpt-5.6-sol",
        "display_name": "GPT-5.6 Sol",
        "owned_by": "openai",
        "access_tier": "free",
        "capabilities": {"vision": True, "tools": True, "reasoning": True, "thinking": True, "deep_search": True},
        "context_length": 128000,
    },
    {
        "id": "gpt-5.6-terra",
        "display_name": "GPT-5.6 Terra",
        "owned_by": "openai",
        "access_tier": "free",
        "capabilities": {"vision": True, "tools": True, "reasoning": True, "thinking": True, "deep_search": True},
        "context_length": 128000,
    },
    {
        "id": "glm-5.2",
        "display_name": "GLM-5.2",
        "owned_by": "zhipu",
        "access_tier": "free",
        "capabilities": {"vision": False, "tools": True, "reasoning": True, "thinking": True, "deep_search": True},
        "context_length": 128000,
    },
    {
        "id": "kimi-k3",
        "display_name": "Kimi K3",
        "owned_by": "moonshot",
        "access_tier": "free",
        "capabilities": {"vision": True, "tools": True, "reasoning": True, "thinking": True, "deep_search": True},
        "context_length": 128000,
    },
]


def fetch_gateway_models(name: str, cfg: dict) -> list[dict]:
    base_url = cfg.get("base_url", "")
    api_key = cfg.get("api_key", "")

    if name == "freemodels":
        return FREEMODELS_CATALOG

    if not base_url:
        return []

    url = base_url.rstrip("/")
    if not url.endswith("/models"):
        url = url.rstrip("/") + "/models"

    try:
        req = urllib.request.Request(url)
        if api_key and api_key != "free":
            req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("User-Agent", "Marzneshin-AgentOS/0.9 DiscoverModels/1.0")

        with urllib.request.urlopen(req, timeout=8.0) as response:
            data = json.loads(response.read().decode("utf-8"))
            models = data.get("data", [])
            for m in models:
                m["_gateway"] = name
            return models
    except Exception as e:
        print(f"  ⚠️  Gateway '{name}': {e}")
        return []


def is_free(model: dict) -> bool:
    mid = model.get("id", "").lower()
    if ":free" in mid or mid.endswith("-free") or "/free" in mid:
        return True
    tier = model.get("access_tier", "").lower()
    if tier == "free":
        return True
    pricing = model.get("pricing", {})
    if pricing and pricing.get("input", 1) == 0 and pricing.get("output", 1) == 0:
        return True
    return False


def has_reasoning(model: dict) -> bool:
    mid = model.get("id", "").lower()
    if any(k in mid for k in ("reason", "deepseek", "glm-5", "qwen3.8", "sol", "terra")):
        return True
    caps = model.get("capabilities", {})
    if caps.get("reasoning"):
        return True
    if model.get("reasoning_efforts"):
        return True
    return False


def has_thinking(model: dict) -> bool:
    mid = model.get("id", "").lower()
    if any(k in mid for k in ("thinking", "think", "fable", "deep-search")):
        return True
    caps = model.get("capabilities", {})
    return caps.get("thinking", False) or caps.get("deep_search", False)


def format_model(model: dict, gateway_name: str = "") -> str:
    mid = model.get("id", "?")
    dname = model.get("display_name", "")
    owner = model.get("owned_by", "?")
    tier = model.get("access_tier", "?")
    ctx = model.get("context_length", 0)
    caps = model.get("capabilities", {})

    tier_icon = "🆓" if is_free(model) else ("💎" if tier == "premium" else "💰")
    reason_icon = "🧠" if has_reasoning(model) else "  "
    think_icon = "💭" if has_thinking(model) else "  "
    vision_icon = "👁" if caps.get("vision") else "  "

    ctx_str = f"{ctx // 1000}K" if ctx >= 1000 else str(ctx)
    gw = gateway_name or model.get("_gateway", "")

    efforts = model.get("reasoning_efforts", {})
    effort_str = ""
    if efforts:
        levels = efforts.get("levels", [])
        if levels:
            effort_str = f" [{','.join(levels)}]"

    name_str = f"{dname}" if dname and dname != mid else ""
    return f"  {tier_icon} {reason_icon} {think_icon} {vision_icon}  [{gw}] {mid:<45} {name_str:<30} ctx:{ctx_str:<8}{effort_str}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover available models from all gateways")
    parser.add_argument("--all", action="store_true", help="Discover from all enabled gateways")
    parser.add_argument("--free", action="store_true", help="Show only free models")
    parser.add_argument("--reasoning", action="store_true", help="Show only models with reasoning capability")
    parser.add_argument("--thinking", action="store_true", help="Show only models with thinking/deep-search")
    parser.add_argument("--gateway", help="Specific gateway to query")
    parser.add_argument("--summary", action="store_true", help="Show compact summary")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if not (args.all or args.free or args.reasoning or args.thinking or args.gateway or args.summary):
        args.all = True

    config = router.load_config()
    gateways = config.get("gateways", {})

    all_models: list[dict] = []
    gateway_counts: dict[str, int] = {}

    print("🔍 Discovering models from configured gateways...\n")

    target_gateways = {args.gateway: gateways[args.gateway]} if args.gateway and args.gateway in gateways else {
        k: v for k, v in gateways.items() if v.get("enabled", True)
    }

    for gw_name, gw_cfg in target_gateways.items():
        print(f"📡 Querying '{gw_name}' ({gw_cfg.get('base_url', '?')})...")
        models = fetch_gateway_models(gw_name, gw_cfg)
        for m in models:
            m["_gateway"] = gw_name
        all_models.extend(models)
        gateway_counts[gw_name] = len(models)
        print(f"   ✅ Found {len(models)} models")

    print(f"\n{'=' * 120}")
    print(f"📊 Total: {len(all_models)} models from {len(gateway_counts)} gateways")
    print(f"{'=' * 120}")

    filtered = all_models
    if args.free:
        filtered = [m for m in filtered if is_free(m)]
        print(f"🆓 Free models: {len(filtered)}")
    if args.reasoning:
        filtered = [m for m in filtered if has_reasoning(m)]
        print(f"🧠 Reasoning models: {len(filtered)}")
    if args.thinking:
        filtered = [m for m in filtered if has_thinking(m)]
        print(f"💭 Thinking/Deep Search models: {len(filtered)}")

    if args.json:
        print(json.dumps(filtered, indent=2, default=str))
        return 0

    if args.summary:
        print(f"\n{'Gateway':<15} {'Total':>6} {'Free':>6} {'Reasoning':>10} {'Thinking':>9}")
        print("-" * 55)
        for gw_name in gateway_counts:
            gw_models = [m for m in all_models if m.get("_gateway") == gw_name]
            n_free = len([m for m in gw_models if is_free(m)])
            n_reason = len([m for m in gw_models if has_reasoning(m)])
            n_think = len([m for m in gw_models if has_thinking(m)])
            print(f"{gw_name:<15} {len(gw_models):>6} {n_free:>6} {n_reason:>10} {n_think:>9}")
        print("-" * 55)
        n_all_free = len([m for m in all_models if is_free(m)])
        n_all_reason = len([m for m in all_models if has_reasoning(m)])
        n_all_think = len([m for m in all_models if has_thinking(m)])
        print(f"{'TOTAL':<15} {len(all_models):>6} {n_all_free:>6} {n_all_reason:>10} {n_all_think:>9}")
    else:
        print(f"\n  Icon Legend: 🆓=Free 💰=Paid 💎=Premium | 🧠=Reasoning 💭=Thinking 👁=Vision\n")
        current_gw = ""
        for m in sorted(filtered, key=lambda x: (x.get("_gateway", ""), x.get("owned_by", ""), x.get("id", ""))):
            gw = m.get("_gateway", "")
            if gw != current_gw:
                print(f"\n── {gw} {'─' * (100 - len(gw))}")
                current_gw = gw
            print(format_model(m, gw))

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
