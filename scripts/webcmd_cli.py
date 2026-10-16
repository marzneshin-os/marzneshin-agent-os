#!/usr/bin/env python3
"""WebCMD Self-Learning Browser Memory CLI (BUILD-SPEC §9).

Unified interactive command-line interface for WebCMD browser memory,
DOM token reduction, sitemap navigation graphs, and session profiles.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import uuid
from datetime import timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib import clock, webcmd_memory
from adapters.webcmd import WebCmdAdapter


def _call_op(adapter: WebCmdAdapter, op: str, payload: dict, dry_run: bool = False):
    deadline = clock.now() + timedelta(seconds=30)
    idem_key = f"cli-webcmd-{op}-{uuid.uuid4().hex[:8]}"
    return adapter.execute(
        op,
        payload,
        idem_key=idem_key,
        idem_class="none",
        deadline=deadline,
        dry_run=dry_run,
        provenance=[{"field": "$.input", "source": "webcmd_cli", "trust": "internal"}],
    )


def print_banner():
    print("""
===================================================================
  🌐 WebCMD Self-Learning Browser Memory CLI · Marzneshin OS
  Capability: 90% Token Reduction & Persistent Sitemap Graph Memory
  Governance: Fail-closed, Cryptographic Receipts, Zero-Leakage (I6)
===================================================================
""")


def cmd_status(adapter: WebCmdAdapter):
    health = adapter.healthz()
    print(f"Adapter Health:   {'🟢 OK' if health.ok else '🔴 FAILED'} ({health.detail})")
    print(f"Latency:          {health.latency_ms:.2f} ms")

    sitemaps = webcmd_memory._load_sitemaps()
    total_domains = len(sitemaps)
    total_routes = sum(len(d.get("routes", {})) for d in sitemaps.values())
    total_shortcuts = sum(len(d.get("shortcuts", {})) for d in sitemaps.values())

    print(f"Cached Domains:   {total_domains}")
    print(f"Learned Routes:   {total_routes}")
    print(f"Action Shortcuts: {total_shortcuts}")

    # Read savings ledger if exists
    ledger_path = webcmd_memory.SAVINGS_LEDGER
    total_tokens_saved = 0
    if ledger_path.exists():
        try:
            with open(ledger_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        total_tokens_saved += entry.get("tokens_saved", 0)
        except Exception:
            pass

    print(f"Tokens Saved:     ~{total_tokens_saved:,} tokens permanently reduced")

    # Node CLI availability
    node_webcmd = shutil.which("webcmd")
    print(f"External WebCMD:  {'🟢 Installed (' + node_webcmd + ')' if node_webcmd else '⚪ Native Python Engine Active (@agentrhq/webcmd optional)'}")


def cmd_browse(adapter: WebCmdAdapter, url: str, profile: str = "default", dry_run: bool = False, as_json: bool = False):
    print(f"Browsing: {url} (Profile: {profile}, Dry-Run: {dry_run})...")
    res = _call_op(adapter, "web_browse", {"url": url, "profile": profile}, dry_run=dry_run)
    if not res.ok:
        print(f"🔴 Error: {res.error}")
        sys.exit(1)

    data = res.data
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    print("\n------------------- Page Summary -------------------")
    print(f"Title:         {data.get('title')}")
    print(f"Raw Size:      {data.get('raw_chars', 0):,} chars")
    print(f"Compressed:    {data.get('compressed_chars', 0):,} chars")
    print(f"Token Savings: {int(data.get('savings_ratio', 0) * 100)}% token reduction")
    print(f"Actions Mapped:{len(data.get('actions', []))} actionable targets")
    print("----------------------------------------------------\n")

    actions = data.get("actions", [])
    if actions:
        print("Interactive Action Targets:")
        for act in actions[:10]:
            print(f"  {act.get('action_id'):<5} [{act.get('tag')}] {act.get('label')[:40]:<40} (sel: {act.get('selector')})")
        if len(actions) > 10:
            print(f"  ... and {len(actions) - 10} more actions")

    print("\nCompressed Text Stream:")
    text = data.get("compressed_text", "")
    print(text[:1500] + ("\n... [truncated]" if len(text) > 1500 else ""))


def cmd_sitemap(domain: str):
    sm = webcmd_memory.get_domain_sitemap(domain)
    if not sm:
        print(f"No cached sitemap found for domain: {domain}")
        return

    print(json.dumps(sm, indent=2, ensure_ascii=False))


def cmd_purge(domain: str | None = None):
    success = webcmd_memory.purge_cache(domain)
    if success:
        target = f"domain '{domain}'" if domain else "all web memory"
        print(f"🟢 Successfully purged {target}")
    else:
        print(f"⚪ No memory found to purge for domain '{domain}'")


def cmd_check_node():
    node_bin = shutil.which("node")
    npm_bin = shutil.which("npm")
    webcmd_bin = shutil.which("webcmd")

    print(f"Node.js binary:  {node_bin or 'Not found'}")
    print(f"npm binary:      {npm_bin or 'Not found'}")
    print(f"webcmd binary:   {webcmd_bin or 'Not found'}")

    if not webcmd_bin:
        print("\nTo install the optional companion CLI from AgentR HQ:")
        print("  npm install -g @agentrhq/webcmd")
        print("  webcmd skills add")
    else:
        print(f"\nWebCMD companion CLI is installed and ready at {webcmd_bin}")


def main():
    parser = argparse.ArgumentParser(description="WebCMD Browser Memory CLI")
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    subparsers.add_parser("status", help="Show WebCMD status and token reduction metrics")

    browse_parser = subparsers.add_parser("browse", help="Browse and compress web page")
    browse_parser.add_argument("url", help="Target URL to browse")
    browse_parser.add_argument("--profile", default="default", help="Session profile name")
    browse_parser.add_argument("--dry-run", action="store_true", help="Do not mutate memory")
    browse_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    sitemap_parser = subparsers.add_parser("sitemap", help="Show sitemap for domain")
    sitemap_parser.add_argument("domain", help="Target domain (e.g. docs.github.com)")

    purge_parser = subparsers.add_parser("purge", help="Purge memory cache")
    purge_parser.add_argument("--domain", default=None, help="Specific domain to purge (default: all)")

    subparsers.add_parser("check-node", help="Check companion node environment")

    args = parser.parse_args()
    if not args.command:
        print_banner()
        parser.print_help()
        sys.exit(0)

    adapter = WebCmdAdapter(world="prod")

    if args.command == "status":
        print_banner()
        cmd_status(adapter)
    elif args.command == "browse":
        cmd_browse(adapter, args.url, profile=args.profile, dry_run=args.dry_run, as_json=args.json)
    elif args.command == "sitemap":
        cmd_sitemap(args.domain)
    elif args.command == "purge":
        cmd_purge(args.domain)
    elif args.command == "check-node":
        cmd_check_node()


if __name__ == "__main__":
    main()
