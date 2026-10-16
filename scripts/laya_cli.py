#!/usr/bin/env python3
"""Laya Typed Decision & Stacking CLI (BUILD-SPEC §9).

Direct interactive interface for Laya-MLX & System 1 Typed Decisions in Marzneshin Autonomous OS.
Enables instant sub-10ms classification, guardrail validation, rubric scoring, and 440x cost reduction stacking.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib import clock, stacking
from adapters.laya import LayaAdapter


def call_op(adapter: LayaAdapter, op: str, payload: dict, dry_run: bool = False):
    deadline = clock.now() + timedelta(seconds=30)
    idem_key = f"cli-laya-{op}-{uuid.uuid4().hex[:8]}"
    return adapter.execute(op, payload, idem_key=idem_key, deadline=deadline, dry_run=dry_run)


def print_banner():
    print("""
===================================================================
  ⚡ Laya Typed Decisions & Stacking CLI · Marzneshin Autonomous OS
  Model: ModernBERT-large 421M / mmBERT-base 322M (Laya-MLX)
  Paradigm: Non-Autoregressive System 1 Fast-Pass (440x Cheaper)
===================================================================
""")


def cmd_status(adapter: LayaAdapter):
    health = adapter.healthz()
    env_res = call_op(adapter, "check_environment", {})
    card_res = call_op(adapter, "get_model_card", {})

    print(f"Health Status:    {'🟢 OK' if health.ok else '🔴 FAILED'} ({health.detail})")
    print(f"Latency:          {health.latency_ms:.2f} ms")
    if env_res.ok:
        env = env_res.data
        print(f"Engine Mode:      {env.get('engine_mode')}")
        print(f"Apple Silicon:    {env.get('apple_silicon_mlx')} (Processor: {env.get('processor')})")
        print(f"RAM Budget:       {env.get('ram_budget_mb')} MB")
    if card_res.ok:
        card = card_res.data
        print(f"Model Backbone:   {card.get('backbone')} ({card.get('parameters')})")
        print(f"Architecture:     {card.get('architecture')}")
        print(f"Tokens/Decision:  {card.get('tokens_per_decision')} (Zero Output Generation)")
        print(f"Cost Profile:     {card.get('cost_profile')}")


def cmd_classify(adapter: LayaAdapter, text: str, categories: list[str]):
    res = call_op(adapter, "classify_intent", {"text": text, "categories": categories})
    if not res.ok:
        print(f"Classification failed: {res.error}")
        return
    data = res.data
    print(f'Text:             "{text}"')
    print(f"Selected:         🎯 {data.get('selected')}")
    print(f"Confidence:       {data.get('confidence') * 100:.1f}%")
    print(f"Probabilities:    {json.dumps(data.get('probabilities', {}), indent=2)}")


def cmd_guardrail(adapter: LayaAdapter, text: str):
    res = call_op(adapter, "guardrail_check", {"text": text})
    if not res.ok:
        print(f"Guardrail check failed: {res.error}")
        return
    data = res.data
    status = "🟢 SAFE" if data.get("is_safe") else "🚨 VIOLATION DETECTED"
    print(f"Status:           {status}")
    print(f"Confidence:       {data.get('confidence') * 100:.1f}%")
    print(f"Violation Prob:   {data.get('violation_probability') * 100:.1f}%")


def cmd_score(adapter: LayaAdapter, text: str, rubric: list[str]):
    res = call_op(adapter, "score_rubric", {"text": text, "rubric": rubric})
    if not res.ok:
        print(f"Scoring failed: {res.error}")
        return
    data = res.data
    print(f"Level:            ⭐ {data.get('level')}")
    print(f"Expected Score:   {data.get('score'):.4f} (0.0 to 1.0)")
    print(f"Confidence:       {data.get('confidence') * 100:.1f}%")


def cmd_stack(adapter: LayaAdapter, prompt: str, criteria: list[str], threshold: float):
    verdict = stacking.evaluate_stack(
        prompt,
        criteria=criteria,
        threshold=threshold,
        adapter=adapter,
    )
    print(f'Prompt:           "{prompt}"')
    print(f"Threshold (tau):  {threshold:.2f}")
    print(f"Decision:         {verdict.decision}")
    print(f"Confidence:       {verdict.confidence * 100:.1f}%")
    print(f"Resolution Route: {'⚡ FAST-PATH (System 1 Resolved)' if verdict.fast_path else '🔄 ESCALATE (System 2 Claude Invoked)'}")
    print(f"Cost Savings:     {verdict.cost_savings_ratio} cheaper ({verdict.tokens_saved} tokens saved)")
    print(f"Latency:          {verdict.latency_ms:.2f} ms")


def main():
    parser = argparse.ArgumentParser(description="Laya Typed Decisions CLI")
    parser.add_argument("--world", default="prod", choices=["prod", "sim"], help="Execution world")
    subparsers = parser.add_subparsers(dest="cmd", help="Subcommand")

    subparsers.add_parser("status", help="Show Laya engine and environment status")

    p_classify = subparsers.add_parser("classify", help="Run intent classification")
    p_classify.add_argument("text", help="Text to classify")
    p_classify.add_argument("--categories", nargs="+", default=["coder", "reviewer", "infra", "billing", "security"])

    p_guard = subparsers.add_parser("guardrail", help="Run guardrail safety verification")
    p_guard.add_argument("text", help="Text to check for injection / policy violation")

    p_score = subparsers.add_parser("score", help="Run rubric scoring")
    p_score.add_argument("text", help="Text to rate")
    p_score.add_argument("--rubric", nargs="+", default=["poor", "acceptable", "excellent"])

    p_stack = subparsers.add_parser("stack", help="Evaluate Jev/Laya + Claude stacking")
    p_stack.add_argument("prompt", help="Prompt to evaluate")
    p_stack.add_argument("--criteria", nargs="+", default=["billing", "technical", "general"])
    p_stack.add_argument("--threshold", type=float, default=0.90)

    args = parser.parse_args()
    if not args.cmd:
        print_banner()
        parser.print_help()
        return

    adapter = LayaAdapter(world=args.world)

    if args.cmd == "status":
        print_banner()
        cmd_status(adapter)
    elif args.cmd == "classify":
        cmd_classify(adapter, args.text, args.categories)
    elif args.cmd == "guardrail":
        cmd_guardrail(adapter, args.text)
    elif args.cmd == "score":
        cmd_score(adapter, args.text, args.rubric)
    elif args.cmd == "stack":
        cmd_stack(adapter, args.prompt, args.criteria, args.threshold)


if __name__ == "__main__":
    main()
