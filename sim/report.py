"""sim/report.py — the scored scenario report (§16).

A scenario that merely "ran" proves nothing. The report scores what the
system did while the world was burning:

  receipt_coverage   every started task has a receipt (target 1.0, I3/G5)
  crash_rate         crashed receipts / total (budget 2%, §14)
  mttr_min           mean ticks from chaos injection to recovery action
  duplicate_work     tasks executed twice with the same idempotency key (target 0)
  guardrail_breaches guardrail.breached events (target 0)
  interventions      human interventions required (target 0 for autonomy)
  token_cost         simulated token spend vs budget
  slo_breaches_min   ticks where CSR < 0.98 (the SLO, §14)

Score = weighted fraction of targets met, 0..1. `expect` thresholds in the
scenario YAML decide pass/fail — "green" is a comparison, not a vibe.
"""

from __future__ import annotations


def build_report(*, scenario: dict, world, fakes: dict, chaos_log: list[dict],
                 actor_stats: dict, wall_clock_s: float, seed: int,
                 duration_h: int, tick_s: int) -> dict:
    expect = scenario.get("expect", {})
    m = world.metrics()

    slo_breach_ticks = actor_stats.get("slo_breach_ticks", 0)
    recoveries = actor_stats.get("recoveries", [])
    mttr_ticks = (sum(r["ticks_to_recover"] for r in recoveries) / len(recoveries)
                  if recoveries else None)

    metrics = {
        "receipt_coverage": actor_stats.get("receipt_coverage", 1.0),
        "crash_rate": actor_stats.get("crash_rate", 0.0),
        "mttr_min": None if mttr_ticks is None else round(mttr_ticks * tick_s / 60, 1),
        "duplicate_work": actor_stats.get("duplicate_work", 0),
        "guardrail_breaches": actor_stats.get("guardrail_breaches", 0),
        "interventions": actor_stats.get("interventions", 0),
        "token_cost_usd": round(actor_stats.get("token_cost_usd", 0.0), 4),
        "slo_breach_min": slo_breach_ticks * tick_s // 60,
        "csr_end": m["csr"],
        "revenue_end_usd": m["revenue_usd"],
        "chaos_fired": len(chaos_log),
    }

    checks = {
        "receipt_coverage >= expect": metrics["receipt_coverage"] >= expect.get("receipt_coverage", 1.0),
        "crash_rate <= expect": metrics["crash_rate"] <= expect.get("crash_rate_max", 0.02),
        "duplicate_work == 0": metrics["duplicate_work"] <= expect.get("duplicate_work_max", 0),
        "guardrail_breaches <= expect": metrics["guardrail_breaches"] <= expect.get("guardrail_breaches_max", 0),
        "interventions <= expect": metrics["interventions"] <= expect.get("interventions_max", 0),
        "slo_breach_min <= expect": metrics["slo_breach_min"] <= expect.get("slo_breach_min_max", 10**9),
        "mttr_min <= expect": (metrics["mttr_min"] is None
                               or metrics["mttr_min"] <= expect.get("mttr_min_max", 10**9)),
    }
    # VS-3 a2a checks — only when the scenario's expect block asks for them,
    # so pre-existing scenarios keep their 7-check shape. VS-4 adds the
    # continuity + kill-switch counters on the same pattern.
    for key, stat in (("a2a_fallbacks_min", "a2a_fallbacks"),
                      ("a2a_completed_min", "a2a_completed"),
                      ("a2a_replayed_min", "a2a_replayed"),
                      ("a2a_failed_max", "a2a_failed"),
                      # VS-4: event seq race regression (ADR-006)
                      ("event_seq_duplicates_max", "event_seq_duplicates"),
                      # VS-4: killswitch_unreadable
                      ("halted_unknown_min", "halted_unknown"),
                      ("halted_killed_min", "halted_killed"),
                      ("fail_closed_engaged_min", "fail_closed_engaged"),
                      ("resumed_after_unknown_min", "resumed_after_unknown"),
                      ("sentinel_receipts_min", "sentinel_receipts"),
                      ("successions_min", "successions"),
                      ("successions_max", "successions"),
                      # VS-4: member_removed (§11.1 executable succession)
                      ("succession_steps_min", "succession_steps"),
                      ("succession_flow_ok_min", "succession_flow_ok"),
                      ("succession_flow_ok_max", "succession_flow_ok"),
                      # VS-4: owner_absent (dead-man switch §11.2)
                      ("l1_executed_min", "l1_executed"),
                      ("l1_queued_min", "l1_queued"),
                      ("l2_halted_ticks_min", "l2_halted_ticks"),
                      ("deadman_hold_ticks_min", "deadman_hold_ticks"),
                      ("deadman_readonly_ticks_min", "deadman_readonly_ticks")):
        if key in expect:
            actual = actor_stats.get(stat, 0)
            if key.endswith("_min"):
                checks[f"{stat} >= expect"] = actual >= expect[key]
            else:
                checks[f"{stat} <= expect"] = actual <= expect[key]
            metrics[stat] = actual
    passed = sum(1 for ok in checks.values() if ok)
    score = round(passed / len(checks), 3)

    return {
        "scenario": scenario.get("name", "unnamed"),
        "seed": seed,
        "duration": {"virtual_hours": duration_h, "tick_s": tick_s,
                     "ticks": world.tick, "wall_clock_s": round(wall_clock_s, 3)},
        "world_end": m,
        "metrics": metrics,
        "checks": checks,
        "checks_passed": f"{passed}/{len(checks)}",
        "score": score,
        "result": "pass" if all(checks.values()) else "fail",
        "chaos_log": chaos_log,
        "recoveries": recoveries,
    }
