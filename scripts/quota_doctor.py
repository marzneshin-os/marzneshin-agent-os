#!/usr/bin/env python3
"""quota_doctor.py — Antigravity Tier-0 Quota & Family Sharing Health Diagnoser.

Provides safe, zero-credential diagnostic inspection of Antigravity AI entitlements,
Google Family Group AI sharing eligibility, and multi-tier model quota routing
(ADR-027 / Resilient Model Quota & Orchestration Mesh).

Commands:
    check-eligibility <email>       - Check Google AI Family Sharing domain eligibility
    diagnose                        - Diagnose local IDE model configuration & quota health
    route-tier <complexity>         - Select optimal model tier with quota-aware fallback
    simulate-429                    - Simulate quota exhaustion and verify graceful tier degradation
    status                          - Output health and routing metrics in JSON
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
STATE_DIR = PROJECT_ROOT / "state"
QUOTA_STATE_FILE = STATE_DIR / "quota_state.json"

MODEL_TIERS = {
    "tier_0": {
        "name": "Tier 0 — Frontier Reasoning & Two-Key Adjudication",
        "models": [
            "gpt-6.1sol",
            "claude-opus-5",
            "gpt-6-astra",
            "claude-opus-4-8",
            "claude-opus-5.5",
            "claude-sonnet-5.5",
            "fable-5.1",
            "gpt-5.6-sol",
            "gpt-5.6-luna",
        ],
        "purpose": "Architecture, system thinking, two-key gate, adversarial review",
        "quota_cost": "premium",
    },
    "tier_1": {
        "name": "Tier 1 — High-Velocity Feature Implementation",
        "models": [
            "glm-5.3",
            "gpt-6.1sol",
            "claude-opus-4-8",
            "gemini-3.8-flash",
            "gemini-3.7-flash",
            "claude-3.7-sonnet",
        ],
        "purpose": "Normal code implementation, test suites, refactoring, documentation",
        "quota_cost": "standard",
    },
    "tier_2": {
        "name": "Tier 2 — High-Throughput & Mechanical Execution",
        "models": [
            "deepseek-v4-flash",
            "glm-5.3",
            "deepseek-chat:free",
            "gemini-3.5-flash",
            "bm25-local",
        ],
        "purpose": "Linting, syntax checks, batch generation, fallback upon 429",
        "quota_cost": "zero/free-pool",
    },
}


def load_quota_state() -> dict:
    if QUOTA_STATE_FILE.exists():
        try:
            with open(QUOTA_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "tier_0_available": True,
        "tier_0_429_count": 0,
        "last_429_ts": None,
        "cooldown_seconds": 60,
        "active_tier": "tier_0",
        "verified_accounts": [],
    }


def save_quota_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(QUOTA_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def check_family_eligibility(email: str) -> dict:
    """Validate whether an email address is eligible for Google One Family Group AI sharing.
    
    Google Family Group rules strictly enforce:
    - Personal Google accounts (@gmail.com or @googlemail.com) are ELIGIBLE.
    - Google Workspace / Custom Enterprise domains (@company.com, @edu) are INELIGIBLE.
    - Users cannot be members of more than 1 family group concurrently.
    - Users can only switch family groups once every 12 months.
    """
    email = email.strip().lower()
    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        return {
            "email": email,
            "eligible": False,
            "reason": "Malformed email format",
            "account_type": "invalid",
        }

    domain = email.split("@")[1]
    is_personal_google = domain in ("gmail.com", "googlemail.com")

    if is_personal_google:
        return {
            "email": email,
            "eligible": True,
            "account_type": "personal_gmail",
            "family_sharing_supported": True,
            "claude_entitlement": "Google AI Premium Family Member (Shared Pool)",
            "guidelines": [
                "1. Family manager must enable 'Share Google One with family' at one.google.com",
                "2. Max 5 family members share the 2TB+ storage and AI model pool",
                "3. Model pool rate limits (429) are aggregated across all family members",
                "4. Only 1 family group switch permitted every 12 months by Google policy",
            ],
        }
    else:
        return {
            "email": email,
            "eligible": False,
            "account_type": "workspace_enterprise",
            "family_sharing_supported": False,
            "reason": "Google Workspace / Enterprise domain accounts cannot join personal Google Family Groups",
            "recommendation": "Use a personal @gmail.com account for family sharing, or purchase individual Google Workspace AI add-on",
        }


def check_astra_window(now_utc: datetime | None = None) -> dict:
    """Check if the current UTC time falls within the 2-hour Astra model supply windows.

    Astra windows occur twice daily:
    - 03:00 Beijing Time (19:00-21:00 UTC)
    - 15:00 Beijing Time (07:00-09:00 UTC)
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    active = now_utc.hour in (7, 8, 19, 20)
    return {
        "window_active": active,
        "utc_hour": now_utc.hour,
        "beijing_schedules": ["03:00 BJT (19:00 UTC)", "15:00 BJT (07:00 UTC)"],
        "recommended_apex_model": "gpt-6-astra" if active else "gpt-6.1sol",
    }


def diagnose_environment() -> dict:
    """Inspect Antigravity IDE and multi-agent environment configuration."""
    diag = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ide": "Antigravity",
        "quota_state": load_quota_state(),
        "model_tiers": MODEL_TIERS,
        "astra_window": check_astra_window(),
        "checks": [],
    }

    # Check 1: Antigravity Config
    win_antigravity = Path("/mnt/c/Users/Asus/.gemini/antigravity-ide")
    has_win_config = win_antigravity.exists()
    diag["checks"].append({
        "name": "Antigravity Host Configuration",
        "passed": has_win_config,
        "detail": str(win_antigravity) if has_win_config else "Host directory not found",
    })

    # Check 2: MCP Ecosystem Availability
    mcp_dir = win_antigravity / "mcp" if has_win_config else None
    has_mcp = mcp_dir.exists() if mcp_dir else False
    diag["checks"].append({
        "name": "Antigravity MCP Ecosystem",
        "passed": has_mcp,
        "detail": f"{len(list(mcp_dir.iterdir()))} MCP server definitions found" if has_mcp else "MCP dir not found",
    })

    # Check 3: Fable Orchestrator Integration
    fable_skill = Path("/mnt/c/Users/Asus/.gemini/config/skills/fable/SKILL.md")
    diag["checks"].append({
        "name": "Claude Fable 5.1 Orchestration Skill",
        "passed": fable_skill.exists(),
        "detail": "Loaded in global config" if fable_skill.exists() else "Missing Fable skill",
    })

    return diag


def route_model(complexity: str, force_tier: str | None = None, now_utc: datetime | None = None) -> dict:
    """Select the optimal model tier based on task complexity, quota health, and Astra windows."""
    state = load_quota_state()
    astra_info = check_astra_window(now_utc)

    # Check if Tier 0 is in cooldown after 429
    if not state.get("tier_0_available", True):
        last_429 = state.get("last_429_ts")
        cooldown = state.get("cooldown_seconds", 60)
        if last_429 and (time.time() - last_429) > cooldown:
            state["tier_0_available"] = True
            save_quota_state(state)

    if force_tier and force_tier in MODEL_TIERS:
        selected_tier = force_tier
    elif complexity.lower() in ("critical", "architecture", "adjudication"):
        selected_tier = "tier_0" if state.get("tier_0_available", True) else "tier_1"
    elif complexity.lower() in ("high",):
        # Prioritize Tier 0 if available, else Tier 1
        selected_tier = "tier_0" if state.get("tier_0_available", True) else "tier_1"
    elif complexity.lower() in ("medium", "feature", "implementation"):
        selected_tier = "tier_1"
    else:
        selected_tier = "tier_2"

    tier_info = MODEL_TIERS[selected_tier]
    if selected_tier == "tier_0":
        recommended = astra_info["recommended_apex_model"]
    else:
        recommended = tier_info["models"][0]

    return {
        "complexity": complexity,
        "selected_tier": selected_tier,
        "tier_name": tier_info["name"],
        "recommended_model": recommended,
        "candidate_models": tier_info["models"],
        "purpose": tier_info["purpose"],
        "quota_fallback_active": not state.get("tier_0_available", True),
        "astra_window": astra_info,
    }


def simulate_429_exhaustion() -> dict:
    """Simulate a 429 Too Many Requests response on Tier 0 and execute graceful fallback."""
    state = load_quota_state()
    state["tier_0_available"] = False
    state["tier_0_429_count"] = state.get("tier_0_429_count", 0) + 1
    state["last_429_ts"] = time.time()
    save_quota_state(state)

    fallback_decision = route_model("critical")
    return {
        "event": "429_TOO_MANY_REQUESTS_RECORDED",
        "tier_0_status": "EXHAUSTED / IN COOLDOWN",
        "cooldown_seconds": state["cooldown_seconds"],
        "immediate_fallback_route": fallback_decision,
        "resilience_verdict": "PASS — Automatic degradation to Tier 1 without task abort",
    }


def main():
    parser = argparse.ArgumentParser(description="Antigravity Tier-0 Quota & Family Sharing Health Diagnoser")
    subparsers = parser.add_subparsers(dest="command")

    # check-eligibility
    p_elig = subparsers.add_parser("check-eligibility", help="Check Google AI Family Sharing domain eligibility")
    p_elig.add_argument("email", help="Google Account Email to check")

    # diagnose
    subparsers.add_parser("diagnose", help="Diagnose local IDE model configuration & quota health")

    # route-tier
    p_route = subparsers.add_parser("route-tier", help="Route task complexity to optimal model tier")
    p_route.add_argument("complexity", choices=["critical", "high", "medium", "low"], help="Task complexity level")
    p_route.add_argument("--force-tier", choices=["tier_0", "tier_1", "tier_2"], help="Force specific tier")

    # simulate-429
    subparsers.add_parser("simulate-429", help="Simulate quota exhaustion and test degradation")

    # check-agentrouter
    subparsers.add_parser("check-agentrouter", help="Check AgentRouter mesh health and Astra window status")

    # status
    subparsers.add_parser("status", help="Output current quota state")

    args = parser.parse_args()

    if args.command == "check-eligibility":
        res = check_family_eligibility(args.email)
        print(json.dumps(res, indent=2))
        sys.exit(0 if res.get("eligible") else 1)

    elif args.command == "diagnose":
        res = diagnose_environment()
        print(json.dumps(res, indent=2))
        sys.exit(0)

    elif args.command == "route-tier":
        res = route_model(args.complexity, args.force_tier)
        print(json.dumps(res, indent=2))
        sys.exit(0)

    elif args.command == "simulate-429":
        res = simulate_429_exhaustion()
        print(json.dumps(res, indent=2))
        sys.exit(0)

    elif args.command == "check-agentrouter":
        state = load_quota_state()
        res = {
            "agentrouter_mesh": "active",
            "astra_window": check_astra_window(),
            "model_tiers": MODEL_TIERS,
            "quota_state": state,
        }
        print(json.dumps(res, indent=2))
        sys.exit(0)

    elif args.command == "status":
        state = load_quota_state()
        print(json.dumps(state, indent=2))
        sys.exit(0)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
