"""adversarial_reviewer.py — Independent Adversarial Reviewer (BUILD-SPEC §10.1, VS-5).

A cross-cutting reviewer role with independent model/prompt lineage
(gpt-4o/adversarial@1). Explicitly tasked with finding reasons to REJECT
changes on critical paths (QA gates, security policy, metric gaming).
Enforces:
  1. No agent approves its own work (author != reviewer).
  2. Independent lineage (reviewer lineage != author lineage).
  3. Gate and policy preservation (no relaxation of safety invariant without Owner ADR).
"""

from __future__ import annotations

import re
from typing import Any

from . import clock, events, paths

REVIEWER_ID = "adversarial-reviewer"
REVIEWER_LINEAGE = "gpt-4o/adversarial@1"

# Patterns that represent critical safety and governance paths.
CRITICAL_PATHS = (
    "scripts/lib/policy.py",
    "scripts/lib/deadman.py",
    "scripts/lib/killswitch.py",
    "scripts/verify.py",
    ".github/workflows/",
    "security/",
)


class ReviewVerdict:
    REJECT = "REJECT"
    APPROVE = "APPROVE"


def review_change(
    *,
    author: str,
    author_lineage: str,
    intent: str,
    changes: list[str] | list[dict[str, Any]],
    diff_text: str = "",
    emit_event: bool = False,
) -> dict[str, Any]:
    """Perform independent adversarial review of a proposed change."""
    rejection_reasons: list[str] = []

    # 1. Rule: Separation of duties (Iron rule / §10: no agent reviews its own work)
    if author == REVIEWER_ID:
        rejection_reasons.append(
            "separation of duties violation: adversarial reviewer cannot review its own work"
        )

    # 2. Rule: Lineage independence
    # Reviewer lineage must be distinct from the author's lineage
    if author_lineage and author_lineage.split("/")[0] == REVIEWER_LINEAGE.split("/")[0]:
        rejection_reasons.append(
            f"lineage collusion: author lineage {author_lineage!r} shares provider/family "
            f"with reviewer lineage {REVIEWER_LINEAGE!r}; review requires independent lineage"
        )

    # Extract paths
    changed_paths: list[str] = []
    for c in changes:
        if isinstance(c, str):
            changed_paths.append(c)
        elif isinstance(c, dict) and "path" in c:
            changed_paths.append(c["path"])

    # 3. Rule: Critical path tampering check
    touches_critical = [p for p in changed_paths if any(p.startswith(cp) or cp in p for cp in CRITICAL_PATHS)]
    if touches_critical:
        # Check diff_text for dangerous weakenings: skipping tests, disabling gates, commenting checks
        dangerous_patterns = [
            r"skip.*test",
            r"#.*verify",
            r"return\s+0.*#.*bypass",
            r"verify.*=.*False",
            r"strict.*=.*False",
        ]
        for pat in dangerous_patterns:
            if diff_text and re.search(pat, diff_text, re.IGNORECASE):
                rejection_reasons.append(
                    f"critical gate relaxation detected on {', '.join(touches_critical)} matching {pat!r}"
                )

    # 4. Rule: Metric gaming check (§10.4)
    if "metric" in intent.lower() or "kpi" in intent.lower():
        if "counter_kpi" not in diff_text and "counter" not in intent.lower():
            rejection_reasons.append(
                "metric gaming risk: KPI modification without corresponding counter-KPI guardrail (§10.4)"
            )

    verdict = ReviewVerdict.REJECT if rejection_reasons else ReviewVerdict.APPROVE
    now_str = clock.iso()

    result = {
        "verdict": verdict,
        "reviewer": REVIEWER_ID,
        "reviewer_lineage": REVIEWER_LINEAGE,
        "author": author,
        "author_lineage": author_lineage,
        "reasons": rejection_reasons,
        "touches_critical": bool(touches_critical),
        "critical_paths": touches_critical,
        "reviewed_at": now_str,
    }

    if emit_event:
        actor = events.Actor(kind="agent", id=REVIEWER_ID)
        event_type = "review.rejected" if verdict == ReviewVerdict.REJECT else "review.approved"
        events.emit(
            event_type,
            actor,
            events.Subject(kind="review", id=f"rev-{author}-{int(clock.now().timestamp())}"),
            {
                "verdict": verdict,
                "author": author,
                "reasons": rejection_reasons,
                "touches_critical": touches_critical,
            },
        )

    return result
