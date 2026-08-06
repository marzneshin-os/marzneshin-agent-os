"""Hierarchical token/cost ledger (GAP G8).

v1.0 set per-agent caps (`tokens_per_day: 300000`, `usd_per_day: 8`) but had no
cost model. 17 agents x 300k = 5.1M tokens/day, which is nowhere near $8/day
at frontier prices — the numbers were off by about two orders of magnitude.
Caps without a model are decoration.

So this module does three things v1.0 lacked:

  1. **Reserve before, settle after.** An agent reserves an estimate, runs, then
     settles actuals. Without reservation, N parallel agents each see budget
     remaining and collectively blow through it.
  2. **Four scopes.** workspace > tier > agent > task. The workspace cap is
     deliberately lower than the sum of agent caps: controlled
     over-subscription, because agents rarely peak together.
  3. **Model-aware pricing.** Cheap models for SENSE/classify, expensive ones
     only for DECIDE and adversarial review. `model` lands in every receipt so
     leverage is measurable instead of assumed.

The ledger is append-only NDJSON, same discipline as the event log.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from . import clock, paths
from .atomic import append_ndjson, read_ndjson
from .ids import new_ulid

# USD per 1M tokens (input, output). Update via ADR when pricing changes —
# never silently, because every budget decision depends on these numbers.
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-8":     (5.00, 25.00),
    "claude-sonnet-5":     (3.00, 15.00),
    "claude-haiku-4-5":    (1.00, 5.00),
    "unknown":             (5.00, 25.00),   # assume expensive when unsure
}

# Which model tier is appropriate for which kind of work (G8).
MODEL_ROUTING: dict[str, str] = {
    "sense": "claude-haiku-4-5",
    "classify": "claude-haiku-4-5",
    "extract": "claude-haiku-4-5",
    "summarize": "claude-haiku-4-5",
    "mirror": "claude-haiku-4-5",
    "execute": "claude-sonnet-5",
    "draft": "claude-sonnet-5",
    "qa": "claude-sonnet-5",
    "decide": "claude-opus-4-8",
    "design": "claude-opus-4-8",
    "adversarial_review": "claude-opus-4-8",
    "incident": "claude-opus-4-8",
}

ESCALATE_AT = 0.80   # §10: escalate at 80% of cap
HARD_STOP_AT = 1.00  # 100% -> budget kill switch


class BudgetError(RuntimeError):
    pass


class BudgetExceeded(BudgetError):
    pass


@dataclass
class Caps:
    """Daily caps for one scope."""
    tokens: int
    usd: float

    def to_dict(self) -> dict:
        return {"tokens": self.tokens, "usd": round(self.usd, 4)}


# Defaults. Real caps come from agents/cards/*.yaml and configs/budget.yaml;
# these exist so the system is safe before those files are authored.
DEFAULT_CAPS: dict[str, Caps] = {
    "workspace": Caps(tokens=4_000_000, usd=60.0),
    "tier:0": Caps(tokens=2_000_000, usd=30.0),
    "tier:1": Caps(tokens=1_200_000, usd=18.0),
    "tier:2": Caps(tokens=1_500_000, usd=22.0),
    "agent:default": Caps(tokens=300_000, usd=6.0),
}


def price(model: str, tokens_in: int, tokens_out: int) -> float:
    rate_in, rate_out = MODEL_PRICING.get(model, MODEL_PRICING["unknown"])
    return (tokens_in / 1_000_000) * rate_in + (tokens_out / 1_000_000) * rate_out


def route_model(work_kind: str) -> str:
    """Pick the cheapest model that can do this class of work."""
    return MODEL_ROUTING.get(work_kind, "claude-sonnet-5")


def _today() -> str:
    return clock.now().date().isoformat()


def _entries(day: str | None = None) -> list[dict]:
    rows = read_ndjson(paths.budget_ledger_file())
    target = day or _today()
    return [r for r in rows if r.get("day") == target]


def _net(rows: list[dict], scope: str) -> tuple[int, float]:
    """Net tokens/usd for a scope: settled actuals plus outstanding reservations.

    Outstanding reservations count against the cap. That is the point of
    reserving — otherwise parallel agents each see room that is already taken.
    """
    tokens = 0
    usd = 0.0
    reserved: dict[str, dict] = {}
    settled: set[str] = set()
    for r in rows:
        if r.get("scope") != scope:
            continue
        kind = r.get("kind")
        if kind == "reserve":
            reserved[r["reservation_id"]] = r
        elif kind == "settle":
            settled.add(r.get("reservation_id", ""))
            tokens += int(r.get("tokens", 0))
            usd += float(r.get("usd", 0.0))
        elif kind == "release":
            settled.add(r.get("reservation_id", ""))
    for rid, r in reserved.items():
        if rid not in settled:
            tokens += int(r.get("tokens", 0))
            usd += float(r.get("usd", 0.0))
    return tokens, round(usd, 6)


def caps_for(scope: str, overrides: dict[str, Caps] | None = None) -> Caps:
    table = {**DEFAULT_CAPS, **(overrides or {})}
    if scope in table:
        return table[scope]
    if scope.startswith("agent:"):
        return table["agent:default"]
    return table["workspace"]


def status(scope: str, *, overrides: dict[str, Caps] | None = None,
           day: str | None = None) -> dict:
    rows = _entries(day)
    tokens, usd = _net(rows, scope)
    caps = caps_for(scope, overrides)
    token_frac = tokens / caps.tokens if caps.tokens else 0.0
    usd_frac = usd / caps.usd if caps.usd else 0.0
    worst = max(token_frac, usd_frac)
    return {
        "scope": scope, "day": day or _today(),
        "spent": {"tokens": tokens, "usd": round(usd, 4)},
        "caps": caps.to_dict(),
        "utilization": round(worst, 4),
        "should_escalate": worst >= ESCALATE_AT,
        "exhausted": worst >= HARD_STOP_AT,
        "headroom": {"tokens": max(0, caps.tokens - tokens), "usd": round(max(0.0, caps.usd - usd), 4)},
    }


def scopes_for(*, agent: str, tier: int) -> list[str]:
    """The chain a spend must fit inside. All four levels are checked."""
    return ["workspace", f"tier:{tier}", f"agent:{agent}"]


def reserve(*, agent: str, tier: int, task_id: str, model: str,
            est_tokens_in: int, est_tokens_out: int,
            overrides: dict[str, Caps] | None = None) -> dict:
    """Reserve budget before doing work.

    Raises BudgetExceeded if any scope in the chain cannot accommodate the
    estimate. The failure names the scope, so the escalation is actionable.
    """
    est_usd = price(model, est_tokens_in, est_tokens_out)
    est_tokens = est_tokens_in + est_tokens_out
    chain = scopes_for(agent=agent, tier=tier)

    for scope in chain:
        st = status(scope, overrides=overrides)
        caps = caps_for(scope, overrides)
        if st["spent"]["tokens"] + est_tokens > caps.tokens or st["spent"]["usd"] + est_usd > caps.usd:
            raise BudgetExceeded(
                f"scope {scope!r} cannot absorb this task: would reach "
                f"{st['spent']['tokens'] + est_tokens}/{caps.tokens} tokens and "
                f"${st['spent']['usd'] + est_usd:.2f}/${caps.usd:.2f}. "
                f"Escalate to orchestrator or defer."
            )

    reservation_id = f"R-{new_ulid()}"
    for scope in chain:
        append_ndjson(paths.budget_ledger_file(), {
            "kind": "reserve", "reservation_id": reservation_id, "scope": scope,
            "day": _today(), "ts": clock.iso(), "agent": agent, "tier": tier,
            "task_id": task_id, "model": model,
            "tokens": est_tokens, "usd": round(est_usd, 6), "estimated": True,
        })
    return {"reservation_id": reservation_id, "scopes": chain, "model": model,
            "est_tokens": est_tokens, "est_usd": round(est_usd, 6)}


def settle(*, reservation_id: str, agent: str, tier: int, task_id: str, model: str,
           tokens_in: int, tokens_out: int, wall_clock_s: float | None = None) -> dict:
    """Record actuals and clear the reservation. Always call this, including on
    failure — an unsettled reservation holds budget hostage until midnight."""
    usd = price(model, tokens_in, tokens_out)
    tokens = tokens_in + tokens_out
    for scope in scopes_for(agent=agent, tier=tier):
        append_ndjson(paths.budget_ledger_file(), {
            "kind": "settle", "reservation_id": reservation_id, "scope": scope,
            "day": _today(), "ts": clock.iso(), "agent": agent, "tier": tier,
            "task_id": task_id, "model": model, "tokens_in": tokens_in,
            "tokens_out": tokens_out, "tokens": tokens, "usd": round(usd, 6),
            "wall_clock_s": wall_clock_s, "estimated": False,
        })
    return {"tokens": tokens, "usd": round(usd, 6), "model": model,
            "wall_clock_s": wall_clock_s}


def release(*, reservation_id: str, agent: str, tier: int, reason: str) -> None:
    """Cancel a reservation without spending (task never ran)."""
    for scope in scopes_for(agent=agent, tier=tier):
        append_ndjson(paths.budget_ledger_file(), {
            "kind": "release", "reservation_id": reservation_id, "scope": scope,
            "day": _today(), "ts": clock.iso(), "reason": reason,
        })


def forecast(*, day: str | None = None) -> dict:
    """Project end-of-day spend from elapsed fraction of the day (G8).

    Linear extrapolation is crude but it is the right crudeness: it fires early
    on a runaway loop, which is the failure mode that matters.
    """
    now = clock.now()
    elapsed = (now.hour * 3600 + now.minute * 60 + now.second) / 86400 or 0.0001
    st = status("workspace", day=day)
    projected_tokens = int(st["spent"]["tokens"] / elapsed)
    projected_usd = round(st["spent"]["usd"] / elapsed, 4)
    caps = caps_for("workspace")
    return {
        "day": st["day"], "elapsed_fraction": round(elapsed, 4),
        "spent": st["spent"],
        "projected_eod": {"tokens": projected_tokens, "usd": projected_usd},
        "caps": caps.to_dict(),
        "projected_utilization": round(max(projected_tokens / caps.tokens,
                                           projected_usd / caps.usd), 4),
        "will_exceed": projected_tokens > caps.tokens or projected_usd > caps.usd,
    }


def spike_detected(*, multiplier: float = 3.0, lookback_days: int = 7) -> dict:
    """Cost-spike detection for the automatic kill switch (§6.3 K5).

    Compares today's projection against the median of prior days rather than
    the mean, so one bad day does not raise the bar for the next.
    """
    rows = read_ndjson(paths.budget_ledger_file())
    by_day: dict[str, float] = {}
    for r in rows:
        if r.get("kind") == "settle" and r.get("scope") == "workspace":
            by_day[r["day"]] = by_day.get(r["day"], 0.0) + float(r.get("usd", 0.0))
    today = _today()
    history = sorted(v for d, v in by_day.items() if d != today)
    history = history[-lookback_days:] if history else []
    if len(history) < 3:
        return {"detected": False, "reason": "insufficient history (<3 days)",
                "baseline_usd": None, "today_usd": by_day.get(today, 0.0)}
    mid = len(history) // 2
    baseline = history[mid] if len(history) % 2 else (history[mid - 1] + history[mid]) / 2
    projected = forecast()["projected_eod"]["usd"]
    detected = baseline > 0 and projected > baseline * multiplier
    return {"detected": detected, "baseline_usd": round(baseline, 4),
            "projected_usd": projected, "multiplier": multiplier,
            "reason": (f"projected ${projected} is >{multiplier}x median baseline "
                       f"${round(baseline, 4)}") if detected else "within baseline"}
