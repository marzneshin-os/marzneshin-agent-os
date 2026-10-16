"""Fake Adapter for Laya Typed Decisions & System 1 Engine.

Must pass the same contract test as the real adapter in sim world (§4).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from adapters.base import (
    Adapter,
    AdapterRefused,
    CircuitBreaker,
    Health,
    IdemClass,
    IdempotencyStore,
    Result,
    deadline_remaining_s,
)


class LayaFake(Adapter):
    name = "laya"

    def __init__(self, world_state=None, *, seed: int = 0, world: str = "sim"):
        self.world = world
        self._w = world_state
        self._circuit = CircuitBreaker()
        self._idem = IdempotencyStore()

        # Injected faults
        self.fail_healthz = False
        self.fail_next_execute = False
        self.fail_as_refused = False
        self.confidence_override: float | None = None

    def healthz(self) -> Health:
        if self.fail_healthz:
            return Health(ok=False, detail="Injected failure in Laya", latency_ms=1.5)
        return Health(ok=True, detail="Laya ModernBERT-421M (simulated standby)", latency_ms=8.0)

    def capabilities(self) -> list[str]:
        return [
            "typed_decision",
            "classify_intent",
            "guardrail_check",
            "score_rubric",
            "stacking_evaluate",
            "check_environment",
            "get_model_card",
        ]

    def execute(
        self,
        op: str,
        payload: dict,
        *,
        idem_key: str,
        idem_class: IdemClass = "scoped",
        dry_run: bool = False,
        deadline: datetime,
        provenance: list[dict] | None = None,
    ) -> Result:
        if op not in self.capabilities():
            return Result(ok=False, op=op, error=f"unknown op: {op}")

        stored = self._idem.lookup(idem_key)
        if stored:
            return stored

        if dry_run:
            res = Result(
                ok=True,
                op=op,
                dry_run=True,
                data={"dry_run": True, "op": op, "status": "simulated_ok"},
            )
            self._idem.save(idem_key, res, klass=idem_class)
            return res

        self._circuit.before_call()

        if deadline_remaining_s(deadline) <= 0:
            return Result(ok=False, op=op, error="deadline exceeded")

        if self.fail_next_execute:
            self.fail_next_execute = False
            if self.fail_as_refused:
                return Result(ok=False, op=op, error="simulated refusal")
            self._circuit.on_failure()
            return Result(ok=False, op=op, error="simulated failure")

        self._circuit.on_success()

        # Handle specific operations
        if op == "get_model_card":
            data = {
                "name": "Laya (Typed Decision Model)",
                "backbone": "ModernBERT-large",
                "parameters": "421M",
                "multilingual_backbone": "mmBERT-base (322M)",
                "architecture": "Non-Autoregressive Bidirectional Encoder",
                "output_heads": ["choice", "score", "noul"],
                "tokens_per_decision": 0,
                "latency_p50_ms": 7.4,
            }
        elif op == "check_environment":
            data = {
                "apple_silicon_mlx": False,
                "engine_mode": "simulation",
                "ram_budget_mb": 687.6,
                "unified_memory_resident": True,
            }
        elif op == "classify_intent":
            text = payload.get("text", "").lower()
            cats = payload.get("categories", ["general"])
            selected = cats[0]
            confidence = self.confidence_override if self.confidence_override is not None else 0.95
            probs = {c: round((1.0 - confidence) / max(1, len(cats) - 1), 4) for c in cats}
            if any(w in text for w in ("syntax", "fix", "code", "test", "refactor", "implement", "bug")):
                if "coder" in cats:
                    selected = "coder"
            elif any(w in text for w in ("review", "qa", "verify", "gate", "audit", "lint")):
                if "reviewer" in cats:
                    selected = "reviewer"
            elif any(w in text for w in ("bill", "refund", "invoice", "duplicate", "payment")):
                if "billing" in cats:
                    selected = "billing"
            probs[selected] = confidence
            data = {
                "selected": selected,
                "confidence": confidence,
                "probabilities": probs,
                "latency_ms": 7.4,
            }
        elif op == "guardrail_check":
            text = payload.get("text", "").lower()
            is_malicious = any(w in text for w in ("ignore", "jailbreak", "kill switch", "reveal", "override", "bypass", "secret"))
            p_violation = 0.92 if is_malicious else 0.02
            data = {
                "is_safe": not is_malicious,
                "violation_detected": is_malicious,
                "confidence": 0.94,
                "violation_probability": p_violation,
            }
        elif op == "score_rubric":
            text = payload.get("text", "").lower()
            rubric = payload.get("rubric", ["poor", "acceptable", "excellent"])
            level = "acceptable"
            score = 0.75
            if any(w in text for w in ("green", "verified", "100%", "excellent", "pass")):
                level = "excellent"
                score = 0.98
            elif any(w in text for w in ("fail", "broken", "poor", "crash", "bug")):
                level = "poor"
                score = 0.15
            data = {
                "level": level,
                "score": score,
                "confidence": 0.91,
                "expected_score": score,
            }
        elif op == "stacking_evaluate":
            prompt = payload.get("prompt", "").lower()
            criteria = payload.get("criteria", ["billing", "technical", "general"])
            threshold = float(payload.get("threshold", 0.90))
            decision = criteria[0]
            confidence = self.confidence_override if self.confidence_override is not None else 0.95
            if any(w in prompt for w in ("bill", "refund", "invoice", "payment")):
                decision = "billing"
            fast_path = confidence >= threshold
            data = {
                "decision": decision,
                "confidence": confidence,
                "fast_path": fast_path,
                "escalate": not fast_path,
                "cost_savings_ratio": "440x",
                "latency_ms": 8.2,
                "tokens_saved": 1200 if fast_path else 0,
                "est_cost_saved_usd": 0.015 if fast_path else 0.0,
            }
        elif op == "typed_decision":
            data = {
                "answers": {
                    q_name: {"answer": "ok", "confidence": 0.95, "probabilities": {"ok": 0.95}}
                    for q_name in payload.get("questions", {})
                }
            }
        else:
            data = {"status": "ok"}

        res = Result(ok=True, op=op, data=data, duration_ms=8.0)
        self._idem.save(idem_key, res, klass=idem_class)
        return res

    def rollback(self, receipt_ref: str) -> Result:
        return Result(ok=True, op="rollback", data={"ref": receipt_ref})
