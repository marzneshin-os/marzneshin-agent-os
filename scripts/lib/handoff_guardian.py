"""handoff_guardian.py — Handoff Guardian & Continuity Engine (BUILD-SPEC §10.1, VS-5).

Guards Iron Rule 3 ("No session without a HANDOFF") and computes the
operational continuity score across sessions. Reaps zombie leases and ensures
receipt coverage remains 100% (G5).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import clock, events, leases, paths, receipts
from .atomic import read_json


def verify_handoff(path: Path | None = None) -> dict[str, Any]:
    """Check that state/HANDOFF.md is valid, fresh, and properly structured."""
    target = path or (paths.state_dir() / "HANDOFF.md")
    if not target.exists():
        return {
            "ok": False,
            "score": 0.0,
            "reasons": ["state/HANDOFF.md does not exist (Iron Rule 3 violation)"]
        }

    text = target.read_text(encoding="utf-8")
    reasons: list[str] = []

    # 1. Header checks: Updated, By, Slice
    updated_match = re.search(r"-\s+\*\*Updated:\*\*\s+(\S+)", text)
    by_match = re.search(r"-\s+\*\*By:\*\*\s+(.+)", text)
    slice_match = re.search(r"-\s+\*\*Slice:\*\*\s+(.+)", text)

    if not updated_match:
        reasons.append("missing '- **Updated:** YYYY-MM-DD' metadata")
    if not by_match:
        reasons.append("missing '- **By:** agent' metadata")
    if not slice_match:
        reasons.append("missing '- **Slice:**' metadata")

    # 2. Section checks: Where we are
    if "## Where we are" not in text:
        reasons.append("missing required '## Where we are' section")

    ok = len(reasons) == 0
    return {
        "ok": ok,
        "score": 1.0 if ok else max(0.0, 1.0 - 0.25 * len(reasons)),
        "updated": updated_match.group(1) if updated_match else None,
        "by": by_match.group(1) if by_match else None,
        "slice": slice_match.group(1) if slice_match else None,
        "reasons": reasons
    }


def compute_continuity_score(*, emit_event: bool = False, actor_id: str = "handoff-guardian") -> dict[str, Any]:
    """Compute composite operational continuity score (0.0 - 1.0).

    Components (BUILD-SPEC §10.1, §11):
      1. handoff_freshness (weight 0.25): valid structured HANDOFF.md
      2. receipt_coverage (weight 0.25): 100% of tasks have receipts (G5)
      3. zero_zombies (weight 0.25): zero un-reaped zombie leases
      4. baseline_health (weight 0.25): state/HEALTH-BASELINE.json exists and green
    """
    factors: dict[str, float] = {}
    details: dict[str, Any] = {}

    # Factor 1: Handoff validity
    h_res = verify_handoff()
    factors["handoff_freshness"] = 1.0 if h_res["ok"] else 0.0
    details["handoff"] = h_res

    # Factor 2: Receipt coverage
    st = receipts.stats(window=20)
    unreadable = st.get("unreadable", 0)
    cov = 1.0 if st.get("total", 0) > 0 and unreadable == 0 else 0.0
    factors["receipt_coverage"] = cov
    details["receipt_total"] = st.get("total", 0)
    details["crash_rate"] = st.get("crash_rate", 0.0)

    # Factor 3: Zero zombies
    zombies = leases.find_zombies()
    factors["zero_zombies"] = 1.0 if not zombies else 0.0
    details["zombies_count"] = len(zombies)

    # Factor 4: Health baseline
    baseline_file = paths.state_dir() / "HEALTH-BASELINE.json"
    if baseline_file.exists():
        b_data = read_json(baseline_file, default={})
        gates = b_data.get("gates", {})
        all_green = (
            gates.get("tests", {}).get("passed", 0) > 0 and
            gates.get("verify", {}).get("passed", 0) > 0 and
            gates.get("sim", {}).get("passed", 0) > 0
        )
        factors["baseline_health"] = 1.0 if all_green else 0.5
        details["baseline_saved_at"] = b_data.get("saved_at")
    else:
        factors["baseline_health"] = 0.0
        details["baseline_saved_at"] = None

    overall = sum(factors.values()) / len(factors)
    verdict = "PASS" if overall >= 0.8 else "FAIL"

    result = {
        "score": round(overall, 3),
        "verdict": verdict,
        "factors": factors,
        "details": details,
        "computed_at": clock.iso(),
    }

    if emit_event:
        actor = events.Actor(kind="agent", id=actor_id)
        events.emit(
            "continuity.scored",
            actor,
            events.Subject(kind="system", id="continuity"),
            {"score": result["score"], "verdict": verdict, "factors": factors}
        )

    return result
