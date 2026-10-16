#!/usr/bin/env python3
"""freellm_cli.py — CLI for FreeLLMAPI Universal Free-Tier Token Pool & Router.

Usage:
    python3 scripts/freellm_cli.py status
    python3 scripts/freellm_cli.py catalog [--domain {coding,reasoning,fast,general}]
    python3 scripts/freellm_cli.py test <provider>
    python3 scripts/freellm_cli.py rotate <provider>
    python3 scripts/freellm_cli.py keys
    python3 scripts/freellm_cli.py add-key <provider> <key>
    python3 scripts/freellm_cli.py export-env
    python3 scripts/freellm_cli.py serve [--port 3001] [--host 127.0.0.1]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

from lib.freellm_pool import (
    FreeLLMPoolManager,
    PROVIDER_CATALOG,
    SmartFallbackRouter,
    KeyVault,
    get_total_free_tier_capacity,
)
from adapters.freellm import FreeLLMAdapter
from adapters.base import IdemClass
from lib import clock, ids


def cmd_status(args: argparse.Namespace) -> int:
    pool = FreeLLMPoolManager()
    status = pool.get_full_pool_status()

    print("=" * 68)
    print("  FreeLLMAPI Universal Free-Tier Token Pool Dashboard")
    print("=" * 68)
    print(f"Total Supported Providers  : {status['total_providers']} providers")
    print(f"Total Configured Keys      : {status['configured_keys']}")
    print(f"Active Operational Keys    : {status['active_keys']}")
    print(f"Keys in Rate-Limit Cooldown: {status['cooldown_keys']}")
    print(f"Estimated Monthly Tokens   : {status['combined_monthly_tokens_estimate']:,} tokens (~7.4B)")
    print("-" * 68)
    print(f"{'PROVIDER':<20} {'STATUS':<10} {'ACTIVE':<8} {'COOLING':<8} {'MONTHLY QUOTA'}")
    print("-" * 68)

    for pid, pdata in sorted(status["providers"].items()):
        is_healthy = pdata["healthy"]
        st = "\033[32mACTIVE\033[0m" if is_healthy else "\033[33mCOOLING\033[0m"
        quota = f"{pdata['quota_monthly']:,}" if pdata["quota_monthly"] else "N/A"
        print(f"{pid:<20} {st:<19} {pdata['active_keys_count']:<8} {pdata['cooldown_keys_count']:<8} {quota}")

    print("=" * 68)
    return 0


def cmd_catalog(args: argparse.Namespace) -> int:
    domain = getattr(args, "domain", None)
    print("=" * 72)
    title = f"FreeLLMAPI Provider & Model Catalog (Domain: {domain})" if domain else "FreeLLMAPI Provider & Model Catalog (34+ Providers)"
    print(f"  {title}")
    print("=" * 72)

    count = 0
    for pid, p in sorted(PROVIDER_CATALOG.items()):
        if domain and domain.lower() not in p.specialties:
            continue
        count += 1
        specs = ", ".join(p.specialties)
        print(f"\n[{p.name}] (ID: {pid})")
        print(f"  Endpoint : {p.base_url}")
        print(f"  Rate     : {p.rpm} RPM | {p.tpm:,} TPM | Monthly: {p.monthly_token_quota:,} tokens")
        print(f"  Focus    : {specs}")
        print(f"  Models   : {', '.join(p.models[:4])}")

    print("\n" + "=" * 72)
    print(f"Total Matching Providers: {count} | Total Token Pool: {get_total_free_tier_capacity():,} tokens/mo")
    print("=" * 72)
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    provider = args.provider.lower().replace("-", "_")
    if provider not in PROVIDER_CATALOG:
        print(f"Error: Unknown provider '{provider}'. Run `catalog` to see available providers.", file=sys.stderr)
        return 1

    print(f"Testing provider '{provider}' ({PROVIDER_CATALOG[provider].name})...")
    adapter = FreeLLMAdapter()
    from datetime import timedelta
    res = adapter.execute(
        "test_provider",
        {"provider": provider},
        idem_key=ids.new_ulid(),
        idem_class="none",
        dry_run=False,
        deadline=clock.now() + timedelta(seconds=10),
        provenance=[],
    )

    if res.ok:
        data = res.data
        print(f"Result: \033[32mSUCCESS\033[0m")
        print(f"  Reachable : {data.get('reachable')}")
        print(f"  Latency   : {data.get('latency_ms', 0):.1f}ms")
        print(f"  Active Keys: {data.get('active_keys', 1)}")
        return 0
    else:
        print(f"Result: \033[31mFAILED\033[0m: {res.error}")
        return 1


def cmd_rotate(args: argparse.Namespace) -> int:
    provider = args.provider.lower().replace("-", "_")
    pool = FreeLLMPoolManager()
    new_key = pool.acquire_key(provider)
    print(f"Rotated key for provider [{provider}]: {KeyVault.redact(new_key)}")
    return 0


def cmd_keys(args: argparse.Namespace) -> int:
    pool_file = REPO / "configs" / "keys_pool.json"
    if not pool_file.exists():
        print("No keys_pool.json found.")
        return 0

    with open(pool_file) as f:
        data = json.load(f)

    print("Configured Key Pools (Securely Redacted):")
    print("-" * 50)
    for p, pdata in data.items():
        active = KeyVault.redact(pdata.get("active_key", ""))
        pool_count = len(pdata.get("pool", []))
        depleted_count = len(pdata.get("depleted", []))
        print(f"Provider: {p:<15} Active: {active:<15} Pool: {pool_count} keys | Depleted: {depleted_count}")
    return 0


def cmd_add_key(args: argparse.Namespace) -> int:
    provider = args.provider.lower().replace("-", "_")
    key = args.key
    pool_file = REPO / "configs" / "keys_pool.json"
    data = {}
    if pool_file.exists():
        with open(pool_file) as f:
            data = json.load(f)

    pentry = data.setdefault(provider, {"active_key": key, "pool": [], "depleted": []})
    if key not in pentry["pool"]:
        pentry["pool"].append(key)
    pentry["active_key"] = key

    with open(pool_file, "w") as f:
        json.dump(data, f, indent=4)

    print(f"Key added to provider [{provider}]. Total keys in pool: {len(pentry['pool'])}")
    return 0


def cmd_export_env(args: argparse.Namespace) -> int:
    port = getattr(args, "port", 3001)
    host = getattr(args, "host", "127.0.0.1")
    endpoint = f"http://{host}:{port}/v1"

    print("# FreeLLMAPI Shell Environment Configuration")
    print("# Copy and paste into your terminal or .env:")
    print(f"export ANTHROPIC_BASE_URL=\"{endpoint}\"")
    print(f"export ANTHROPIC_API_KEY=\"free\"")
    print(f"export OPENAI_BASE_URL=\"{endpoint}\"")
    print(f"export OPENAI_API_KEY=\"free\"")
    print(f"export CLAUDE_BASE_URL=\"{endpoint}\"")
    print(f"export FREELLM_BASE_URL=\"{endpoint}\"")
    print(f"\n# To test Claude Code with FreeLLMAPI:")
    print(f"# claude --api-url {endpoint}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from router_server import main as serve_main
    return serve_main(["--host", args.host, "--port", str(args.port)])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FreeLLMAPI Universal Free-Tier Token Pool CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # status
    p_status = sub.add_parser("status", help="Show pool status and key health")
    p_status.set_defaults(func=cmd_status)

    # catalog
    p_cat = sub.add_parser("catalog", help="List supported free-tier providers and models")
    p_cat.add_argument("--domain", choices=["coding", "reasoning", "fast", "eval", "general"], help="Filter by domain specialty")
    p_cat.set_defaults(func=cmd_catalog)

    # test
    p_test = sub.add_parser("test", help="Test connectivity to a provider")
    p_test.add_argument("provider", help="Provider ID (e.g. groq, google_gemini, cerebras)")
    p_test.set_defaults(func=cmd_test)

    # rotate
    p_rot = sub.add_parser("rotate", help="Rotate key for provider")
    p_rot.add_argument("provider", help="Provider ID")
    p_rot.set_defaults(func=cmd_rotate)

    # keys
    p_keys = sub.add_parser("keys", help="List configured keys in pool")
    p_keys.set_defaults(func=cmd_keys)

    # add-key
    p_add = sub.add_parser("add-key", help="Add an API key to a provider pool")
    p_add.add_argument("provider", help="Provider ID")
    p_add.add_argument("key", help="API key string")
    p_add.set_defaults(func=cmd_add_key)

    # export-env
    p_env = sub.add_parser("export-env", help="Print shell export statements for Claude Code / Cursor / OpenCode")
    p_env.add_argument("--port", type=int, default=3001)
    p_env.add_argument("--host", default="127.0.0.1")
    p_env.set_defaults(func=cmd_export_env)

    # serve
    p_serve = sub.add_parser("serve", help="Run local FreeLLMAPI proxy server")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=3001)
    p_serve.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
