"""Liveness and Readiness health endpoints (§5.3: GET /healthz, GET /readyz)."""

from __future__ import annotations

from fastapi import APIRouter, Response, status
from scripts.lib import killswitch

router = APIRouter()


@router.get("/healthz")
def liveness() -> dict:
    return {"status": "ok", "live": True, "version": "2.0.0"}


@router.get("/readyz")
def readiness(response: Response) -> dict:
    try:
        ks = killswitch.check()
        verdict = ks.verdict.value if hasattr(ks.verdict, "value") else str(ks.verdict)
        if verdict != "running":
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {
                "status": "unavailable",
                "ready": False,
                "killswitch": verdict,
                "detail": ks.detail,
            }
        return {
            "status": "ok",
            "ready": True,
            "killswitch": "running",
            "freshness_seconds": round(ks.freshness_seconds, 2),
        }
    except Exception as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "error", "ready": False, "error": str(exc)}
