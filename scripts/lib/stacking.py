"""Stacking Engine — System 1 (Laya Typed Decisions) + System 2 (Claude / Heavy LLM).

Implements the high-performance stacking architecture inspired by:
  - Video: "How to Stack Jev AI With Claude in 90-Seconds (440x Cheaper)"
  - Model: mizorewww/laya-mlx & convaiinnovations/laya ModernBERT-large 421M

Workflow:
  1. Fast System 1 pass: evaluates input through Laya non-autoregressive decision heads (<10ms, 0 tokens).
  2. Mathematical calibration: checks output confidence against threshold tau (default 0.90).
  3. Fast-path: if confidence >= tau, returns the typed result immediately (440x cost reduction, 95% latency reduction).
  4. Escalation: if confidence < tau or creative prose/code generation is required, escalates to Claude/OmniRoute.
  5. Metrics & Ledger: records tokens saved and cost reduction.

No module-level external imports. Strict stdlib only for verify.py --lint-imports compliance.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from . import clock, paths, router


@dataclass
class StackingVerdict:
    """The result of a stacked System 1 / System 2 evaluation."""
    decision: Any
    confidence: float
    fast_path: bool
    escalate: bool
    cost_savings_ratio: str = "440x"
    tokens_saved: int = 0
    latency_ms: float = 0.0
    est_cost_saved_usd: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "confidence": self.confidence,
            "fast_path": self.fast_path,
            "escalate": self.escalate,
            "cost_savings_ratio": self.cost_savings_ratio,
            "tokens_saved": self.tokens_saved,
            "latency_ms": self.latency_ms,
            "est_cost_saved_usd": self.est_cost_saved_usd,
            "metadata": self.metadata,
        }


def get_laya_adapter(world: str = "prod"):
    """Lazily load the Laya adapter to avoid circular or top-level import violations."""
    try:
        from adapters.laya import LayaAdapter
        return LayaAdapter(world=world)
    except Exception:
        from sim.fakes.laya import LayaFake
        return LayaFake(world="sim")


def evaluate_stack(
    prompt: str,
    *,
    criteria: list[str] | None = None,
    threshold: float = 0.90,
    task_type: str = "choice",
    world: str = "prod",
    adapter: Any | None = None,
) -> StackingVerdict:
    """Run System 1 (Laya) pass and decide whether to resolve via fast-path or escalate to Claude."""
    if criteria is None:
        criteria = ["billing", "technical", "general"]

    laya = adapter or get_laya_adapter(world=world)
    now = clock.now()
    deadline_ts = now + timedelta(seconds=10)

    payload = {
        "prompt": prompt,
        "criteria": criteria,
        "threshold": threshold,
        "task_type": task_type,
    }

    try:
        res = laya.execute(
            "stacking_evaluate",
            payload,
            idem_key=f"stack-{abs(hash(prompt))}-{int(threshold*100)}",
            deadline=deadline_ts,
        )
        if res.ok:
            d = res.data
            verdict = StackingVerdict(
                decision=d.get("decision"),
                confidence=float(d.get("confidence", 0.0)),
                fast_path=bool(d.get("fast_path", False)),
                escalate=bool(d.get("escalate", True)),
                cost_savings_ratio="440x" if d.get("fast_path") else "1x",
                tokens_saved=int(d.get("tokens_saved", 0)),
                latency_ms=float(d.get("latency_ms", 8.0)),
                est_cost_saved_usd=float(d.get("est_cost_saved_usd", 0.0)),
                metadata={"engine": d.get("runtime", "laya")},
            )
            record_stacking_metrics(verdict)
            return verdict
    except Exception:
        # Fail-closed: On any failure in System 1, escalate to System 2
        pass

    return StackingVerdict(
        decision=criteria[0] if criteria else None,
        confidence=0.0,
        fast_path=False,
        escalate=True,
        cost_savings_ratio="1x",
        tokens_saved=0,
        latency_ms=0.0,
        est_cost_saved_usd=0.0,
        metadata={"error": "fail_closed_escalated"},
    )


def record_stacking_metrics(verdict: StackingVerdict) -> None:
    """Record savings telemetry in the state budget directory."""
    try:
        ledger_path = paths.repo_root() / "state" / "budget" / "stacking_savings.ndjson"
        paths.ensure_parent(ledger_path)
        entry = {
            "ts": clock.now().isoformat(),
            "fast_path": verdict.fast_path,
            "escalate": verdict.escalate,
            "confidence": verdict.confidence,
            "tokens_saved": verdict.tokens_saved,
            "est_cost_saved_usd": verdict.est_cost_saved_usd,
        }
        with open(ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass
