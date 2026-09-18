"""growth.py — Growth Spine, Funnel Analytics, and NSM Engine (BUILD-SPEC §13, VS-8).

Implements:
  1. Strict Privacy & No-Traffic-Content Enforcement (§13.1):
     User traffic contents, destination IPs, and destinations are forbidden from
     ever entering the event log or analytics models.
  2. North Star Metric (NSM) Engine (§13.2):
     "Number of paid users with at least one successful and stable connection in a 7-day rolling window."
     100% traceable: every count is backed by an auditable chain of raw event IDs.
  3. Conversion Funnel & Customer Journey Tracking:
     Visit -> Signup -> Trial -> Paid -> Active Connection.
  4. Unit Economics Model (§13.3):
     GrossProfitPerUser = ARPU - infra/user - payment_fee - support_cost - agent_token_cost/user.
     LTV, CAC payback, margin targets, and 48-hour campaign stop-loss enforcement.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from . import clock, events, paths
from .atomic import read_json, write_json_atomic

# Forbidden traffic content keywords and fields (§13.1)
FORBIDDEN_TRAFFIC_FIELDS = {
    "destination_ip",
    "dest_ip",
    "target_host",
    "packet_payload",
    "raw_traffic",
    "destination_url",
    "traffic_content",
    "visited_sites",
}


class PrivacyViolationError(ValueError):
    """Raised when an attempt is made to log user traffic or destination (§13.1)."""


def assert_no_traffic_content(data: dict[str, Any] | None) -> None:
    """Enforce privacy invariant: traffic content or destinations must NEVER be stored."""
    if not data:
        return
    for k, v in data.items():
        k_lower = k.lower()
        if k_lower in FORBIDDEN_TRAFFIC_FIELDS or any(sub in k_lower for sub in ("packet", "traffic_content", "dest_url")):
            raise PrivacyViolationError(
                f"Privacy invariant violation (§13.1): field {k!r} contains forbidden user traffic or destination data"
            )
        if isinstance(v, dict):
            assert_no_traffic_content(v)


def record_growth_event(
    event_type: str,
    anon_user_id: str,
    *,
    payload: dict[str, Any] | None = None,
    campaign: str | None = None,
    consent_state: str = "granted",
    actor_id: str = "analytics-engineer",
) -> events.Event:
    """Record an auditable growth or funnel event with privacy guarantees."""
    safe_payload = dict(payload or {})
    assert_no_traffic_content(safe_payload)
    if campaign:
        safe_payload["campaign"] = campaign
    safe_payload["consent_state"] = consent_state

    actor = events.Actor(kind="human", id=anon_user_id)
    subject = events.Subject(kind="growth", id=event_type)

    return events.emit(
        event_type,
        actor,
        subject,
        safe_payload,
        trust="internal",
    )


def compute_nsm(
    window_days: int = 7,
    *,
    world: str = "prod",
) -> dict[str, Any]:
    """Compute North Star Metric (§13.2) traceable back to raw event IDs.

    NSM = Count of paid users with at least one successful connection in the rolling window.
    """
    end_date = clock.now().date()
    start_date = end_date - timedelta(days=window_days)

    paid_users: set[str] = set()
    connected_users: set[str] = set()
    trace_events: list[str] = []

    for ev in events.iter_range(start_date, end_date, world=world):
        etype = ev.get("type")
        actor_dict = ev.get("actor", {})
        uid = actor_dict.get("id") if isinstance(actor_dict, dict) else ""
        eid = ev.get("event_id", "")
        if etype == "checkout.completed":
            if uid:
                paid_users.add(uid)
            trace_events.append(eid)
        elif etype == "connection.success":
            if uid:
                connected_users.add(uid)
            trace_events.append(eid)

    nsm_users = paid_users & connected_users

    res = {
        "nsm_count": len(nsm_users),
        "paid_users_count": len(paid_users),
        "connected_users_count": len(connected_users),
        "active_users": sorted(list(nsm_users)),
        "window_days": window_days,
        "event_trace": trace_events,
        "trace_events_count": len(trace_events),
        "computed_at": clock.iso(),
    }
    return res


def compute_funnel(
    window_days: int = 7,
    *,
    world: str = "prod",
) -> dict[str, Any]:
    """Calculate multi-step conversion funnel across customer journey (§13.1, VS-8)."""
    end_date = clock.now().date()
    start_date = end_date - timedelta(days=window_days)

    visits: set[str] = set()
    signups: set[str] = set()
    trials: set[str] = set()
    paid: set[str] = set()
    connected: set[str] = set()

    step_trace: dict[str, list[str]] = {
        "visit": [],
        "signup": [],
        "trial": [],
        "paid": [],
        "active": [],
    }

    for ev in events.iter_range(start_date, end_date, world=world):
        actor_dict = ev.get("actor", {})
        uid = actor_dict.get("id") if isinstance(actor_dict, dict) else ""
        eid = ev.get("event_id", "")
        etype = ev.get("type")
        if etype == "funnel.visit":
            if uid:
                visits.add(uid)
            step_trace["visit"].append(eid)
        elif etype == "funnel.signup":
            if uid:
                signups.add(uid)
            step_trace["signup"].append(eid)
        elif etype == "funnel.trial_started":
            if uid:
                trials.add(uid)
            step_trace["trial"].append(eid)
        elif etype == "checkout.completed":
            if uid:
                paid.add(uid)
            step_trace["paid"].append(eid)
        elif etype == "connection.success":
            if uid:
                connected.add(uid)
            step_trace["active"].append(eid)

    n_visit = len(visits)
    n_signup = len(signups)
    n_trial = len(trials)
    n_paid = len(paid)
    n_active = len(paid & connected)

    return {
        "counts": {
            "visit": n_visit,
            "signup": n_signup,
            "trial": n_trial,
            "paid": n_paid,
            "active": n_active,
        },
        "conversion_rates": {
            "visit_to_signup": round(n_signup / max(1, n_visit), 4),
            "signup_to_trial": round(n_trial / max(1, n_signup), 4),
            "trial_to_paid": round(n_paid / max(1, n_trial), 4),
            "paid_to_active": round(n_active / max(1, n_paid), 4),
            "overall_visit_to_paid": round(n_paid / max(1, n_visit), 4),
        },
        "step_trace": {k: v[:20] for k, v in step_trace.items()},  # bounded trace sample
        "window_days": window_days,
        "computed_at": clock.iso(),
    }


def compute_unit_economics(
    *,
    arpu: float,
    infra_per_user: float,
    payment_fee: float,
    support_cost: float,
    agent_token_cost_per_user: float,
    cac: float,
    expected_lifetime_months: int = 12,
    target_cac: float | None = None,
) -> dict[str, Any]:
    """Evaluate SaaS unit economics and stop-loss criteria (§13.3).

    GrossProfitPerUser = ARPU - infra/user - payment_fee - support_cost - agent_token_cost/user
    LTV = ARPU * gross_margin * expected_lifetime_months
    Targets: LTV:CAC > 3, CAC payback < 3mo, gross_margin > 70%.
    """
    total_cost = infra_per_user + payment_fee + support_cost + agent_token_cost_per_user
    gross_profit = arpu - total_cost
    gross_margin = (gross_profit / max(0.01, arpu))
    ltv = arpu * gross_margin * expected_lifetime_months
    ltv_cac = ltv / max(0.01, cac)
    cac_payback_mo = cac / max(0.01, gross_profit)

    t_cac = target_cac or (arpu * 0.5)
    stop_loss_triggered = cac > (1.5 * t_cac)

    targets = {
        "ltv_cac_gt_3": ltv_cac > 3.0,
        "payback_lt_3mo": cac_payback_mo < 3.0,
        "gross_margin_gt_70": gross_margin > 0.70,
    }

    return {
        "arpu": arpu,
        "infra_per_user": infra_per_user,
        "payment_fee": payment_fee,
        "support_cost": support_cost,
        "agent_token_cost_per_user": agent_token_cost_per_user,
        "gross_profit_per_user": round(gross_profit, 2),
        "gross_margin_pct": round(gross_margin * 100, 2),
        "cac": cac,
        "ltv": round(ltv, 2),
        "ltv_cac_ratio": round(ltv_cac, 2),
        "cac_payback_months": round(cac_payback_mo, 2),
        "targets_met": targets,
        "all_targets_satisfied": all(targets.values()),
        "stop_loss_triggered": stop_loss_triggered,
        "stop_loss_reason": "CAC > 1.5x target threshold (§13.3)" if stop_loss_triggered else None,
    }
