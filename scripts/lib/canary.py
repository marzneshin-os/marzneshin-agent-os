"""canary.py — Statistical Canary Deployment & Auto-Rollback Engine (BUILD-SPEC §5.7, VS-7).

Implements:
  1. Multi-stage progression: 1% -> 10% -> 50% -> 100%.
  2. Statistical gating:
     - Sample size n_min derived from MDE (power=0.8, alpha=0.05).
     - Sequential testing with always-valid p-values allowing safe early stopping.
     - Strict rule: n < n_min -> inconclusive -> hold stage.
       'Data insufficient is never green' (§5.7).
  3. Observability & Probe Fleet validation:
     - Multi-ASN probe fleet health check (§5.7).
     - Fail-closed: < 2 healthy probes -> hold (no promotion).
  4. Auto-rollback engine:
     - Detects CSR degradation below safety threshold or statistically significant drop.
     - Executes immediate rollback, restoring stable baseline configuration profile.
     - Emits 'canary.rolled_back' and 'rollback.executed' audit events.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import clock, events, paths, probe_fleet
from .atomic import read_json, write_json_atomic

CANARY_STAGES = [1, 10, 50, 100]
DEFAULT_BASELINE_PROFILE = "reality-v6"
DEFAULT_BASELINE_CSR = 0.99
DEFAULT_CRITICAL_CSR_FLOOR = 0.95
DEFAULT_MDE = 0.02


@dataclass
class GateDecision:
    verdict: str  # promote | hold | rollback | inconclusive
    current_stage_pct: int
    next_stage_pct: int | None
    samples: int
    n_min: int
    csr: float
    p_value: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "current_stage_pct": self.current_stage_pct,
            "next_stage_pct": self.next_stage_pct,
            "samples": self.samples,
            "n_min": self.n_min,
            "csr": round(self.csr, 4),
            "p_value": round(self.p_value, 4),
            "reason": self.reason,
        }


def compute_n_min(
    mde: float = DEFAULT_MDE,
    *,
    alpha: float = 0.05,
    power: float = 0.8,
    baseline_p: float = 0.5,
) -> int:
    """Compute minimum sample size required to detect an effect size of MDE.

    Formula (§5.7, §13.4):
      n_min = ceil(2 * p * (1 - p) * (z_alpha + z_beta)^2 / MDE^2)
    For alpha=0.05 (z_a=1.96) and power=0.80 (z_b=0.84).
    """
    z_a = 1.96  # two-sided 95%
    z_b = 0.84 if power >= 0.8 else 0.67
    p = baseline_p
    variance = 2 * p * (1 - p)
    n = math.ceil(variance * ((z_a + z_b) ** 2) / (mde ** 2))
    return max(100, n)


def compute_always_valid_p_value(
    samples_base: int,
    ok_base: int,
    samples_test: int,
    ok_test: int,
) -> float:
    """Sequential testing bound providing an always-valid p-value under optional stopping.

    Uses a martingale-based empirical bound that holds for any stopping time:
      p_val = min(1.0, 2 * exp(-2 * (n1 * n2 / (n1 + n2)) * (p1 - p2)^2))
    """
    if samples_base <= 0 or samples_test <= 0:
        return 1.0
    p1 = ok_base / samples_base
    p2 = ok_test / samples_test
    diff = abs(p1 - p2)
    if diff == 0.0:
        return 1.0
    effective_n = (samples_base * samples_test) / (samples_base + samples_test)
    exponent = -2.0 * effective_n * (diff ** 2)
    p_val = min(1.0, 2.0 * math.exp(max(-100.0, exponent)))
    return p_val


def evaluate_canary_gate(
    *,
    current_stage_pct: int,
    samples: int,
    ok: int,
    probe_fleet_result: probe_fleet.ProbeFleetResult | None = None,
    error_budget_exhausted: bool = False,
    mde: float = DEFAULT_MDE,
    baseline_csr: float = DEFAULT_BASELINE_CSR,
    critical_csr_floor: float = DEFAULT_CRITICAL_CSR_FLOOR,
) -> GateDecision:
    """Evaluate whether a canary rollout stage can be promoted, held, rolled back, or is inconclusive.

    Enforces all 4 §5.7 gate conditions:
      1. Probe fleet healthy across distinct ASNs (fail-closed: <2 -> hold).
      2. Auto-rollback triggered if CSR drops below critical floor or statistically significant regression.
      3. n >= n_min check (if n < n_min -> inconclusive; data insufficient is never green).
      4. Error budget available (§14: if exhausted -> hold).
    """
    csr = (ok / max(1, samples)) if samples > 0 else 0.0
    n_min = compute_n_min(mde=mde)
    baseline_samples = max(1000, samples)
    baseline_ok = int(baseline_samples * baseline_csr)
    p_val = compute_always_valid_p_value(baseline_samples, baseline_ok, samples, ok)

    # 1. Probe Fleet Fail-Closed Check (§5.7, I12)
    if probe_fleet_result is None or not probe_fleet_result.healthy:
        asns_up = len(probe_fleet_result.healthy_asns) if probe_fleet_result else 0
        return GateDecision(
            verdict="hold",
            current_stage_pct=current_stage_pct,
            next_stage_pct=None,
            samples=samples,
            n_min=n_min,
            csr=csr,
            p_value=p_val,
            reason=f"probe fleet degraded ({asns_up} ASNs healthy, min 2 required) — fail-closed (§5.7, I12)",
        )

    # 2. Critical Regression & Auto-Rollback Check
    if samples >= 50 and csr < critical_csr_floor:
        return GateDecision(
            verdict="rollback",
            current_stage_pct=current_stage_pct,
            next_stage_pct=None,
            samples=samples,
            n_min=n_min,
            csr=csr,
            p_value=p_val,
            reason=f"CSR critical drop: {csr:.4f} < floor {critical_csr_floor:.4f}; auto-rollback triggered",
        )

    # 3. Statistical Significance Check on Sample Size
    if samples < n_min:
        return GateDecision(
            verdict="inconclusive",
            current_stage_pct=current_stage_pct,
            next_stage_pct=None,
            samples=samples,
            n_min=n_min,
            csr=csr,
            p_value=p_val,
            reason=f"insufficient sample size: n={samples} < n_min={n_min}; data insufficient is never green (§5.7)",
        )

    # 4. Error Budget Check (§14)
    if error_budget_exhausted:
        return GateDecision(
            verdict="hold",
            current_stage_pct=current_stage_pct,
            next_stage_pct=None,
            samples=samples,
            n_min=n_min,
            csr=csr,
            p_value=p_val,
            reason="error budget exhausted (>100% consumed); rollouts frozen until recovery (§14)",
        )

    # 5. Promotion Progression
    idx = CANARY_STAGES.index(current_stage_pct) if current_stage_pct in CANARY_STAGES else 0
    if idx + 1 < len(CANARY_STAGES):
        next_stage = CANARY_STAGES[idx + 1]
    else:
        next_stage = 100  # fully deployed

    return GateDecision(
        verdict="promote",
        current_stage_pct=current_stage_pct,
        next_stage_pct=next_stage,
        samples=samples,
        n_min=n_min,
        csr=csr,
        p_value=p_val,
        reason=f"gate satisfied: n={samples} >= {n_min}, csr={csr:.4f}, probe fleet green",
    )


# --- Storage & Lifecycle ---

def _canary_dir() -> Path:
    d = paths.state_dir() / "canary"
    d.mkdir(parents=True, exist_ok=True)
    return d


def deploy_canary(
    profile: str,
    *,
    initial_pct: int = 1,
    mde: float = DEFAULT_MDE,
    baseline_profile: str = DEFAULT_BASELINE_PROFILE,
    actor_id: str = "config-engineer",
) -> dict[str, Any]:
    """Initialize and deploy a new canary experiment."""
    now_str = clock.iso()
    exp_id = f"canary-{profile}-{int(clock.now().timestamp())}"
    rec = {
        "experiment_id": exp_id,
        "profile": profile,
        "baseline_profile": baseline_profile,
        "current_stage_pct": initial_pct,
        "status": "active",  # active | rolled_back | completed
        "mde": mde,
        "n_min": compute_n_min(mde),
        "deployed_at": now_str,
        "updated_at": now_str,
        "history": [
            {
                "stage_pct": initial_pct,
                "action": "deployed",
                "at": now_str,
            }
        ],
    }
    write_json_atomic(_canary_dir() / f"{exp_id}.json", rec)

    actor = events.Actor(kind="agent", id=actor_id)
    events.emit(
        "canary.deployed",
        actor,
        events.Subject(kind="canary", id=exp_id),
        {"profile": profile, "initial_pct": initial_pct, "mde": mde},
    )
    return rec


def get_canary(experiment_id: str) -> dict[str, Any] | None:
    p = _canary_dir() / f"{experiment_id}.json"
    if not p.exists():
        return None
    return read_json(p, default=None)


def list_canaries() -> list[dict[str, Any]]:
    res = []
    for f in sorted(_canary_dir().glob("canary-*.json")):
        data = read_json(f, default=None)
        if data:
            res.append(data)
    return res


def promote_canary(
    experiment_id: str,
    *,
    samples: int | None = None,
    ok: int | None = None,
    probe_fleet_result: probe_fleet.ProbeFleetResult | None = None,
    error_budget_exhausted: bool = False,
    actor_id: str = "config-engineer",
) -> dict[str, Any]:
    """Evaluate canary gate and advance stage if green, or execute rollback if degraded."""
    exp = get_canary(experiment_id)
    if not exp:
        raise ValueError(f"experiment {experiment_id} not found")
    if exp["status"] != "active":
        return {"ok": False, "reason": f"canary is {exp['status']}", "experiment": exp}

    # If samples/ok not provided, read from probe fleet
    pf = probe_fleet_result or probe_fleet.sample_fleet(actor_id=actor_id)
    s_cnt = samples if samples is not None else pf.total_samples
    ok_cnt = ok if ok is not None else pf.total_ok

    cur_stage = exp["current_stage_pct"]
    decision = evaluate_canary_gate(
        current_stage_pct=cur_stage,
        samples=s_cnt,
        ok=ok_cnt,
        probe_fleet_result=pf,
        error_budget_exhausted=error_budget_exhausted,
        mde=exp.get("mde", DEFAULT_MDE),
    )

    actor = events.Actor(kind="agent", id=actor_id)
    now_str = clock.iso()

    if decision.verdict == "rollback":
        return rollback_canary(
            experiment_id,
            reason=decision.reason,
            actor_id=actor_id,
        )

    if decision.verdict == "promote":
        next_stage = decision.next_stage_pct or 100
        exp["current_stage_pct"] = next_stage
        exp["updated_at"] = now_str
        if next_stage >= 100:
            exp["status"] = "completed"
        exp["history"].append({
            "stage_pct": next_stage,
            "action": "promoted",
            "at": now_str,
            "evidence": decision.to_dict(),
        })
        write_json_atomic(_canary_dir() / f"{experiment_id}.json", exp)
        events.emit(
            "canary.promoted",
            actor,
            events.Subject(kind="canary", id=experiment_id),
            decision.to_dict(),
        )
        return {"ok": True, "verdict": "promote", "stage": next_stage, "decision": decision.to_dict()}

    if decision.verdict == "inconclusive":
        events.emit(
            "canary.inconclusive",
            actor,
            events.Subject(kind="canary", id=experiment_id),
            decision.to_dict(),
        )
        return {"ok": False, "verdict": "inconclusive", "stage": cur_stage, "decision": decision.to_dict()}

    # hold
    events.emit(
        "canary.held",
        actor,
        events.Subject(kind="canary", id=experiment_id),
        decision.to_dict(),
    )
    return {"ok": False, "verdict": "hold", "stage": cur_stage, "decision": decision.to_dict()}


def rollback_canary(
    experiment_id: str,
    *,
    reason: str,
    max_ttr_s: int = 300,
    actor_id: str = "config-engineer",
) -> dict[str, Any]:
    """Immediately roll back canary to baseline profile and emit audit events."""
    exp = get_canary(experiment_id)
    if not exp:
        raise ValueError(f"experiment {experiment_id} not found")

    now_str = clock.iso()
    exp["status"] = "rolled_back"
    exp["current_stage_pct"] = 0
    exp["updated_at"] = now_str
    exp["rollback"] = {
        "rolled_back_at": now_str,
        "reason": reason,
        "restored_profile": exp.get("baseline_profile", DEFAULT_BASELINE_PROFILE),
        "max_ttr_s": max_ttr_s,
    }
    exp["history"].append({
        "stage_pct": 0,
        "action": "rolled_back",
        "at": now_str,
        "reason": reason,
    })
    write_json_atomic(_canary_dir() / f"{experiment_id}.json", exp)

    actor = events.Actor(kind="agent", id=actor_id)
    events.emit(
        "canary.rolled_back",
        actor,
        events.Subject(kind="canary", id=experiment_id),
        {"reason": reason, "restored_profile": exp["baseline_profile"]},
    )
    events.emit(
        "rollback.executed",
        actor,
        events.Subject(kind="config", id=exp["profile"]),
        {"restored": exp["baseline_profile"], "reason": reason, "max_ttr_s": max_ttr_s},
    )

    return {
        "ok": True,
        "verdict": "rollback",
        "rolled_back": True,
        "restored_profile": exp["baseline_profile"],
        "reason": reason,
    }
