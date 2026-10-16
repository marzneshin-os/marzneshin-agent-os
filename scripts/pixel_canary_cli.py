#!/usr/bin/env python3
"""Pixel Canary CLI Runner (BUILD-SPEC §9).

Direct interactive interface for Pixel Canary (stealth/pixel-canary)
in Marzneshin Autonomous OS.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import timedelta
from pathlib import Path

# Add repo root and scripts/lib to sys.path per D6 invariant
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib import clock
from adapters.pixel_canary import PixelCanaryAdapter
from eval.nextjs_agent_evals import OFFICIAL_BENCHMARK_RESULTS, BENCHMARK_TASKS


def call_op(adapter: PixelCanaryAdapter, op: str, payload: dict, dry_run: bool = False):
    deadline = clock.now() + timedelta(seconds=30)
    idem_key = f"cli-{op}-{uuid.uuid4().hex[:8]}"
    return adapter.execute(op, payload, idem_key=idem_key, deadline=deadline, dry_run=dry_run)


def print_banner():
    print("""
===================================================================
  🚀 Pixel Canary CLI · Marzneshin Autonomous OS
  Model: stealth/pixel-canary (90% pass@4 Next.js Evals · FREE)
===================================================================
""")


def cmd_status(adapter: PixelCanaryAdapter):
    print("[*] Checking Pixel Canary Environment & Model Card...")
    env_res = call_op(adapter, "check_environment", {})
    card_res = call_op(adapter, "get_model_card", {})
    
    print("\n[+] Status Report:")
    for k, v in env_res.data.items():
        print(f"    • {k}: {v}")
        
    print("\n[+] Benchmarks & Identity:")
    for k, v in card_res.data.get("benchmarks", {}).items():
        print(f"    • {k}: {v}")
    print()


def cmd_chat(adapter: PixelCanaryAdapter, prompt: str, sim: bool = False):
    print(f"[*] Sending prompt to Pixel Canary...")
    if sim:
        adapter.world = "sim"
    res = call_op(adapter, "chat_completion", {"prompt": prompt})
    if res.ok:
        print("\n--- [Pixel Canary Response] ---")
        print(res.data.get("content", ""))
        print("-------------------------------")
        print(f"[✔] Cost: ${res.data.get('cost_usd', 0.00):.2f} (FREE)")
        print(f"[✔] Duration: {res.duration_ms:.1f}ms\n")
    else:
        print(f"\n[✘] Error: {res.error}")
        if "Authentication failed" in str(res.error) or "401" in str(res.error):
            print("\n[💡 Tip] To use live Vercel AI Gateway without Cline, set VERCEL_GATEWAY_KEY in .env")
            print("         Alternatively, run with --sim for simulated zero-cost local execution.")


def cmd_eval(adapter: PixelCanaryAdapter, target: str):
    code = target
    path = Path(target)
    if path.exists() and path.is_file():
        code = path.read_text(encoding="utf-8")
        print(f"[*] Evaluating code from file: {path}")
    else:
        print(f"[*] Evaluating inline code snippet...")

    res = call_op(adapter, "evaluate_code", {"code": code})
    if res.ok:
        data = res.data
        print(f"\n[+] Status: {data.get('status')} (Score: {data.get('eval_score') * 100:.0f}%)")
        print("    Checks:")
        for check, passed in data.get("checks", {}).items():
            mark = "✔" if passed else "✘"
            print(f"      [{mark}] {check}")
        print()


def cmd_benchmark():
    print("[*] Official Next.js Agent Evals Leaderboard (Source: nextjs.org/evals, Sep 25, 2026):\n")
    print(f"{'Rank':<6} {'Model':<26} {'pass@4':<10} {'Cost/Task':<12} {'Value / Status'}")
    print("-" * 72)
    for i, m in enumerate(OFFICIAL_BENCHMARK_RESULTS, 1):
        star = "★ " if m.highlight else "  "
        cost_str = "FREE" if m.cost_per_task_usd == 0 else f"${m.cost_per_task_usd:.2f}"
        print(f"{star}{i:<4} {m.name:<26} {m.pass4_rate*100:.0f}%{'':<6} {cost_str:<12} {m.badge}")
    print("-" * 72)
    print(f"\n[+] Total Benchmark Tasks in Suite: {len(BENCHMARK_TASKS)}")
    for t in BENCHMARK_TASKS:
        print(f"    • [{t['id']}] {t['title']} ({t['difficulty']}) - {t['category']}")
    print()


def cmd_savings(adapter: PixelCanaryAdapter, count: int):
    res = call_op(adapter, "calculate_cost_savings", {"tasks_count": count})
    if res.ok:
        d = res.data
        print(f"\n[💰] Cost Savings for {count:,} Autonomous Tasks:")
        print(f"    • Pixel Canary Cost:   ${d['pixel_canary_cost_usd']:.2f} (FREE)")
        print(f"    • GPT 6 Astra Cost:    ${d['gpt6_astra_cost_usd']:.2f}")
        print(f"    • Claude Fable 5.1:    ${d['claude_fable_cost_usd']:.2f}")
        print(f"    ------------------------------------")
        print(f"    💰 Net Savings vs GPT 6:     +${d['savings_vs_gpt6_usd']:.2f} (100% saved)")
        print(f"    💰 Net Savings vs Fable:     +${d['savings_vs_fable_usd']:.2f} (100% saved)\n")


def main():
    parser = argparse.ArgumentParser(description="Pixel Canary CLI for Marzneshin OS")
    parser.add_argument("--status", action="store_true", help="Show model status and health")
    parser.add_argument("--chat", type=str, help="Send prompt to Pixel Canary")
    parser.add_argument("--eval", type=str, help="Evaluate Next.js code or file path")
    parser.add_argument("--benchmark", action="store_true", help="Display Next.js Agent Evals benchmark suite")
    parser.add_argument("--savings", type=int, default=0, help="Calculate savings for N tasks")
    parser.add_argument("--sim", action="store_true", help="Force simulated offline response")
    
    args = parser.parse_args()
    print_banner()

    adapter = PixelCanaryAdapter()

    if args.status:
        cmd_status(adapter)
    elif args.chat:
        cmd_chat(adapter, args.chat, sim=args.sim)
    elif args.eval:
        cmd_eval(adapter, args.eval)
    elif args.benchmark:
        cmd_benchmark()
    elif args.savings > 0:
        cmd_savings(adapter, args.savings)
    else:
        cmd_status(adapter)
        print("💡 Quick Examples:")
        print("   python3 scripts/pixel_canary_cli.py --chat \"Create a Server Action in Next.js 15\" --sim")
        print("   python3 scripts/pixel_canary_cli.py --benchmark")
        print("   python3 scripts/pixel_canary_cli.py --savings 1000")
        print("   python3 scripts/pixel_canary_cli.py --eval \"export async function action() { 'use server'; }\"")


if __name__ == "__main__":
    main()
