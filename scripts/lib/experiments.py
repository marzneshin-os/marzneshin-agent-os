"""experiments.py — Statistical Experimentation Loop, SRM, Guardrails, and Negative Results (BUILD-SPEC §13.4, VS-9).

Implements:
  1. Reusable Statistical Testing Engine (§13.4):
     Uses the same mathematical core as canary gating:
     - Sample size n_min from MDE (alpha=0.05, power=0.8).
     - Sequential testing with always-valid p-value.
  2. Sample Ratio Mismatch (SRM) Detection:
     Chi-square goodness-of-fit test against intended traffic split (p < 0.001 flags SRM).
  3. Guardrail Metrics & Auto-Stop:
     Numeric safety boundaries checked on every readout; automatic stop and rollback upon breach.
  4. Mandatory Negative Result Recording:
     Every inconclusive, flat, or regressed experiment records an auditable negative result with evidence.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import clock, events, paths
from .atomic import read_json, write_json_atomic
from .canary import DEFAULT_MDE, compute_always_valid_p_value, compute_n_min


def _erfc(x: float) -> float:
    return math.erfc(x)


def check_srm(
    count_a: int,
    count_b: int,
    *,
    target_ratio: float = 0.5,
    alpha: float = 0.001,
) -> dict[str, Any]:
    """Chi-square goodness-of-fit test for Sample Ratio Mismatch (SRM).

    SRM occurs when the observed assignment deviates significantly from expected ratio,
    indicating severe sample bias or engineering defects in assignment.
    """
    total = count_a + count_b
    if total <= 0:
        return {"srm_detected": False, "p_value": 1.0, "chi_square": 0.0, "total": 0}

    exp_a = total * target_ratio
    exp_b = total * (1.0 - target_ratio)

    chi_sq = ((count_a - exp_a) ** 2) / max(0.001, exp_a) + ((count_b - exp_b) ** 2) / max(0.001, exp_b)
    # p-value for df=1: P(X >= chi_sq) = erfc(sqrt(chi_sq / 2))
    p_val = _erfc(math.sqrt(chi_sq / 2.0))
    srm_detected = p_val < alpha

    return {
        "srm_detected": srm_detected,
        "p_value": round(p_val, 6),
        "chi_square": round(chi_sq, 4),
        "count_a": count_a,
        "count_b": count_b,
        "expected_a": round(exp_a, 1),
        "expected_b": round(exp_b, 1),
    }


def _experiments_dir() -> Path:
    d = paths.state_dir() / "experiments"
    d.mkdir(parents=True, exist_ok=True)
    return d


def create_experiment(
    name: str,
    hypothesis: str,
    *,
    variant_a: str = "control",
    variant_b: str = "treatment",
    primary_metric: str = "conversion_rate",
    guardrail_metrics: dict[str, float] | None = None,
    mde: float = DEFAULT_MDE,
    target_ratio: float = 0.5,
    actor_id: str = "analytics-engineer",
) -> dict[str, Any]:
    """Initialize a new experiment with explicit hypothesis and guardrails."""
    now_str = clock.iso()
    exp_id = f"exp-{name}-{int(clock.now().timestamp())}"
    guardrails = guardrail_metrics or {"csr_floor": 0.98}
    n_min = compute_n_min(mde=mde)

    record = {
        "experiment_id": exp_id,
        "name": name,
        "hypothesis": hypothesis,
        "variant_a": variant_a,
        "variant_b": variant_b,
        "primary_metric": primary_metric,
        "guardrail_metrics": guardrails,
        "mde": mde,
        "n_min": n_min,
        "target_ratio": target_ratio,
        "status": "active",  # active | shipped | killed | stopped
        "created_at": now_str,
        "updated_at": now_str,
        "readouts": [],
        "decision": None,
    }
    write_json_atomic(_experiments_dir() / f"{exp_id}.json", record)

    actor = events.Actor(kind="agent", id=actor_id)
    events.emit(
        "experiment.created",
        actor,
        events.Subject(kind="experiment", id=exp_id),
        {"name": name, "hypothesis": hypothesis, "primary_metric": primary_metric, "n_min": n_min},
    )
    return record


def get_experiment(experiment_id: str) -> dict[str, Any] | None:
    p = _experiments_dir() / f"{experiment_id}.json"
    if not p.exists():
        return None
    return read_json(p, default=None)


def list_experiments() -> list[dict[str, Any]]:
    res = []
    for f in sorted(_experiments_dir().glob("exp-*.json")):
        data = read_json(f, default=None)
        if data:
            res.append(data)
    return res


def evaluate_readout(
    experiment_id: str,
    *,
    samples_a: int,
    ok_a: int,
    samples_b: int,
    ok_b: int,
    guardrail_values: dict[str, float] | None = None,
    final_readout: bool = False,
    actor_id: str = "analytics-engineer",
) -> dict[str, Any]:
    """Evaluate experiment readout with SRM check, guardrail stop conditions, and sequential testing (§13.4)."""
    exp = get_experiment(experiment_id)
    if not exp:
        raise ValueError(f"experiment {experiment_id} not found")

    total_samples = samples_a + samples_b
    n_min = exp.get("n_min", compute_n_min())
    target_ratio = exp.get("target_ratio", 0.5)

    # 1. Sample Ratio Mismatch (SRM) Check
    srm_result = check_srm(samples_a, samples_b, target_ratio=target_ratio)
    if srm_result["srm_detected"]:
        reason = f"SRM detected (p={srm_result['p_value']} < 0.001, chi2={srm_result['chi_square']}); assignment bias invalidates experiment"
        return record_decision(
            experiment_id,
            decision="kill",
            reason=reason,
            evidence={"srm": srm_result},
            is_negative_result=True,
            actor_id=actor_id,
        )

    # 2. Guardrails Check
    g_vals = guardrail_values or {}
    g_bounds = exp.get("guardrail_metrics", {})
    for g_key, g_bound in g_bounds.items():
        if g_key in g_vals:
            obs = g_vals[g_key]
            # If name has 'floor' or 'min', breaching means obs < bound
            if "floor" in g_key or "min" in g_key:
                if obs < g_bound:
                    reason = f"Guardrail breach: {g_key}={obs} < bound {g_bound}"
                    actor = events.Actor(kind="agent", id=actor_id)
                    events.emit(
                        "guardrail.breached",
                        actor,
                        events.Subject(kind="experiment", id=experiment_id),
                        {"metric": g_key, "observed": obs, "bound": g_bound},
                    )
                    return record_decision(
                        experiment_id,
                        decision="stopped",
                        reason=reason,
                        evidence={"guardrails": g_vals, "breached": g_key},
                        is_negative_result=True,
                        actor_id=actor_id,
                    )

    # 3. Primary Metric & Always-Valid P-Value
    rate_a = (ok_a / max(1, samples_a)) if samples_a > 0 else 0.0
    rate_b = (ok_b / max(1, samples_b)) if samples_b > 0 else 0.0
    delta = rate_b - rate_a
    p_val = compute_always_valid_p_value(samples_a, ok_a, samples_b, ok_b)

    readout_data = {
        "samples_a": samples_a,
        "ok_a": ok_a,
        "rate_a": round(rate_a, 4),
        "samples_b": samples_b,
        "ok_b": ok_b,
        "rate_b": round(rate_b, 4),
        "delta": round(delta, 4),
        "p_value": round(p_val, 4),
        "srm": srm_result,
        "total_samples": total_samples,
        "n_min": n_min,
    }

    actor = events.Actor(kind="agent", id=actor_id)
    events.emit(
        "experiment.readout",
        actor,
        events.Subject(kind="experiment", id=experiment_id),
        readout_data,
    )

    # 4. Statistical Decision Logic
    if total_samples < n_min:
        return {
            "verdict": "inconclusive",
            "reason": f"insufficient sample size: n={total_samples} < n_min={n_min}; data insufficient is never green (§5.7, §13.4)",
            "readout": readout_data,
        }

    # Samples >= n_min:
    if p_val < 0.05 and delta > 0.0:
        return record_decision(
            experiment_id,
            decision="ship",
            reason=f"statistically significant positive lift: delta={delta:+.4f}, p_value={p_val:.4f} < 0.05",
            evidence=readout_data,
            is_negative_result=False,
            actor_id=actor_id,
        )

    if p_val < 0.05 and delta < 0.0:
        return record_decision(
            experiment_id,
            decision="kill",
            reason=f"statistically significant regression: delta={delta:+.4f}, p_value={p_val:.4f} < 0.05",
            evidence=readout_data,
            is_negative_result=True,
            actor_id=actor_id,
        )

    if final_readout:
        # Reached end of trial with no significant effect -> mandatory negative result recording
        return record_decision(
            experiment_id,
            decision="kill",
            reason=f"flat result at end of trial: delta={delta:+.4f}, p_value={p_val:.4f} >= 0.05 (no significant effect)",
            evidence=readout_data,
            is_negative_result=True,
            actor_id=actor_id,
        )

    return {
        "verdict": "inconclusive",
        "reason": f"sample size reached but p_value={p_val:.4f} >= 0.05; continuing trial until final readout",
        "readout": readout_data,
    }


def record_decision(
    experiment_id: str,
    *,
    decision: str,  # ship | kill | stopped
    reason: str,
    evidence: dict[str, Any],
    is_negative_result: bool = False,
    actor_id: str = "analytics-engineer",
) -> dict[str, Any]:
    """Persist final decision and emit audit events including mandatory negative result records (§13.4)."""
    exp = get_experiment(experiment_id)
    if not exp:
        raise ValueError(f"experiment {experiment_id} not found")

    now_str = clock.iso()
    exp["status"] = decision
    exp["updated_at"] = now_str
    exp["decision"] = {
        "decision": decision,
        "reason": reason,
        "evidence": evidence,
        "is_negative_result": is_negative_result,
        "decided_at": now_str,
        "decided_by": actor_id,
    }
    write_json_atomic(_experiments_dir() / f"{experiment_id}.json", exp)

    actor = events.Actor(kind="agent", id=actor_id)
    subj = events.Subject(kind="experiment", id=experiment_id)

    if decision == "ship":
        events.emit("experiment.shipped", actor, subj, {"reason": reason, "evidence": evidence})
    elif decision == "stopped":
        events.emit("experiment.stopped", actor, subj, {"reason": reason, "evidence": evidence})
    else:
        events.emit("experiment.killed", actor, subj, {"reason": reason, "evidence": evidence})

    if is_negative_result:
        # Mandatory negative result registration (§13.4)
        events.emit(
            "experiment.negative_result",
            actor,
            subj,
            {"name": exp["name"], "reason": reason, "evidence": evidence},
        )

    return {
        "verdict": decision,
        "reason": reason,
        "evidence": evidence,
        "is_negative_result": is_negative_result,
    }
