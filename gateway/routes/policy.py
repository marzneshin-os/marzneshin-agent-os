"""Policy dry-run evaluation endpoint (§5.3: POST /v1/policy/evaluate)."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter
from pydantic import BaseModel

from scripts.lib import policy, killswitch

router = APIRouter(prefix="/v1", tags=["policy"])


class PolicyEvaluateRequest(BaseModel):
    capability: str
    sender: str
    target: str
    autonomy_requested: str = "L2"
    inputs: dict[str, Any] = {}


@router.post("/policy/evaluate")
def evaluate_policy(req: PolicyEvaluateRequest) -> dict:
    ks = killswitch.check()
    ks_verdict = ks.verdict.value if hasattr(ks.verdict, "value") else str(ks.verdict)
    
    if ks_verdict != "running":
        return {
            "verdict": "DENY",
            "allowed": False,
            "reason": f"Kill switch active: {ks_verdict}",
            "killswitch_engaged": True,
        }

    autonomy_num = 2
    if req.autonomy_requested.startswith("L"):
        try:
            autonomy_num = int(req.autonomy_requested[1:])
        except ValueError:
            autonomy_num = 2

    res = policy.evaluate(
        capability=req.capability,
        agent=req.sender,
        autonomy_requested=autonomy_num,
        dry_run=True,
    )

    verdict_str = res.decision.name if hasattr(res.decision, "name") else str(res.decision)
    allowed = verdict_str in {"ALLOW", "ALLOW_WITH_LEASE"}
    return {
        "verdict": verdict_str,
        "allowed": allowed,
        "capability": req.capability,
        "operation_class": res.operation_class,
        "autonomy_granted": f"L{res.autonomy_granted}",
        "reason": res.reason,
        "guardrails": res.guardrails,
        "killswitch_engaged": False,
    }
