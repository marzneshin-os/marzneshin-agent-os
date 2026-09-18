"""Combo engine and quota tracker for LLM gateway (9Router and Claude Code Router).

No network I/O. Safe for lint-imports.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import atomic, clock, paths
from .tokensaver import TokenSaverResult


# ---------------------------------------------------------------------------
# Configuration & Models
# ---------------------------------------------------------------------------

_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z0-9_]+)(?::-([^}]*))?\}")


def expand_env_vars(val: Any) -> Any:
    """Recursively expand ${VAR:-default} and ${VAR} patterns."""
    if isinstance(val, str):
        def repl(match: re.Match) -> str:
            var_name = match.group(1)
            default_val = match.group(2) if match.group(2) is not None else ""
            return os.environ.get(var_name, default_val)
        return _ENV_VAR_PATTERN.sub(repl, val)
    elif isinstance(val, dict):
        return {k: expand_env_vars(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [expand_env_vars(x) for x in val]
    return val


@dataclass
class GatewayConfig:
    flavor: str    # "ccr" | "ninerouter" | "omniroute" | "openai"
    base_url: str
    api_key: str = ""
    enabled: bool = True
    description: str = ""


@dataclass
class ProviderConfig:
    name: str
    gateways: list[str]
    max_retries: int = 2
    enabled: bool = True


@dataclass
class ComboConfig:
    name: str
    strategy: str  # "fallback" | "round_robin" | "fusion"
    members: list[str]  # e.g., ["ccr:FreeLLMAPI/deepseek-v4-pro", "gemini/gemini-3.6-flash"]


def router_usage_file() -> Path:
    """Return the usage log path."""
    return paths.router_usage_file()


def load_config() -> dict[str, Any]:
    """Load configs/router.json with environment variable expansion."""
    config_file = paths.repo_root() / "configs" / "router.json"
    if not config_file.exists():
        return {"gateways": {}, "providers": {}, "combos": {}, "quota": {}}
    try:
        raw = atomic.read_json(config_file)
        return expand_env_vars(raw)
    except Exception:
        return {"gateways": {}, "providers": {}, "combos": {}, "quota": {}}


# ---------------------------------------------------------------------------
# Error Classification
# ---------------------------------------------------------------------------

class RouteError(Exception):
    pass


class QuotaExhaustedError(RouteError):
    pass


class ProviderFailedError(RouteError):
    pass


def classify_error(status_code: int, response_body: str = "") -> str:
    """Map HTTP status to internal error class."""
    if status_code == 429 or status_code == 402:
        if "quota" in response_body.lower() or "insufficient" in response_body.lower() or status_code == 402:
            return "quota_exhausted"
        return "rate_limited"
    if status_code == 401 or status_code == 403:
        return "auth_failed"
    if status_code >= 500:
        return "provider_error"
    return "unknown"


# ---------------------------------------------------------------------------
# Quota Tracker
# ---------------------------------------------------------------------------

@dataclass
class QuotaUsage:
    requests_5h: int = 0
    requests_daily: int = 0
    requests_weekly: int = 0
    requests_monthly: int = 0

    def to_dict(self) -> dict:
        return {
            "5h": self.requests_5h,
            "daily": self.requests_daily,
            "weekly": self.requests_weekly,
            "monthly": self.requests_monthly,
        }


def _get_usage_file() -> Path:
    usage_file = router_usage_file()
    paths.ensure_parent(usage_file)
    return usage_file


def record_usage(model: str, is_combo: bool, tokens: int, rtk_metrics: TokenSaverResult | None = None) -> None:
    """Append a usage record to the router ledger."""
    now = clock.now()
    record = {
        "ts": now.isoformat(),
        "date": now.date().isoformat(),
        "model": model,
        "is_combo": is_combo,
        "tokens": tokens,
    }
    if rtk_metrics:
        record["rtk"] = rtk_metrics.to_dict()
    
    usage_file = _get_usage_file()
    with open(usage_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def get_daily_usage(date_str: str | None = None) -> int:
    """Return total tokens consumed on the given date (defaults to today)."""
    if not date_str:
        date_str = clock.now().date().isoformat()
    usage_file = router_usage_file()
    if not usage_file.exists():
        return 0
    total = 0
    with open(usage_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                rec_date = rec.get("date")
                if not rec_date and "ts" in rec:
                    rec_date = rec["ts"][:10]
                if rec_date == date_str:
                    total += rec.get("tokens", 0)
            except Exception:
                continue
    return total


def check_quota(model: str, limit_daily: int = 1000) -> QuotaUsage:
    """Read usage.ndjson and sum up requests for this model in windows."""
    usage_file = _get_usage_file()
    if not usage_file.exists():
        return QuotaUsage()

    now = clock.now()
    q = QuotaUsage()
    
    with open(usage_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if record.get("model") != model:
                    continue
                
                ts_str = record.get("ts")
                if not ts_str:
                    continue
                    
                import datetime
                record_ts = datetime.datetime.fromisoformat(ts_str)
                delta = now - record_ts
                
                if delta.total_seconds() <= 5 * 3600:
                    q.requests_5h += 1
                if delta.days == 0:
                    q.requests_daily += 1
                if delta.days <= 7:
                    q.requests_weekly += 1
                if delta.days <= 30:
                    q.requests_monthly += 1
                    
            except Exception:
                continue

    if limit_daily > 0 and q.requests_daily >= limit_daily:
        raise QuotaExhaustedError(f"daily quota exhausted for {model}")
        
    return q


# ---------------------------------------------------------------------------
# Combo Engine
# ---------------------------------------------------------------------------

def normalize_model(model_string: str) -> str:
    """Ensure provider/model or ccr:provider/model format."""
    if model_string.startswith("ccr:"):
        return model_string
    if ":" in model_string:
        return model_string
    if "/" not in model_string:
        if model_string.startswith("gemini"):
            return f"gemini/{model_string}"
        if model_string.startswith("gpt"):
            return f"openai/{model_string}"
        if model_string.startswith("claude"):
            return f"anthropic/{model_string}"
        return f"unknown/{model_string}"
    return model_string


def get_combo_strategy(combo_name: str) -> ComboConfig | None:
    """Resolve a combo name to its strategy and members (supports both list and dict formats)."""
    config = load_config()
    combos = config.get("combos", {})
    if combo_name in combos:
        c = combos[combo_name]
        if isinstance(c, list):
            return ComboConfig(
                name=combo_name,
                strategy="fallback",
                members=[normalize_model(m) for m in c]
            )
        elif isinstance(c, dict):
            return ComboConfig(
                name=combo_name,
                strategy=c.get("strategy", "fallback"),
                members=[normalize_model(m) for m in c.get("members", [])]
            )
    return None
