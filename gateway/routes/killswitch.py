"""Killswitch read-only status endpoint (§5.3: GET /v1/killswitch).

Rule I14: Activation is NEVER solely via T3 HTTP Gateway.
"""

from __future__ import annotations

from fastapi import APIRouter
from scripts.lib import killswitch

router = APIRouter(prefix="/v1", tags=["killswitch"])


@router.get("/killswitch")
def get_killswitch_status() -> dict:
    ks = killswitch.check()
    verdict = ks.verdict.value if hasattr(ks.verdict, "value") else str(ks.verdict)
    entries = []
    for e in ks.entries:
        entries.append({
            "source": e.source,
            "scope": e.scope.value if hasattr(e.scope, "value") else str(e.scope),
            "reason": e.reason,
            "engaged_at": e.engaged_at,
        })
    return {
        "verdict": verdict,
        "active": verdict != "running",
        "checked_at": ks.checked_at,
        "freshness_seconds": round(ks.freshness_seconds, 2),
        "sources_consulted": ks.sources_consulted,
        "entries": entries,
        "detail": ks.detail,
        "rule_i14_notice": "Killswitch activation is external/fail-closed; this endpoint is read-only.",
    }
