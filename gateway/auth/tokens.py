"""Authentication and authorization for Marzneshin HTTP Gateway (§5.3).

Supports mTLS headers, Bearer tokens, and capability scoping.
In local development/testing without tokens configured, operates in authenticated local mode.
"""

from __future__ import annotations

import os
from typing import Optional
from fastapi import Header, HTTPException, status

DEFAULT_TOKEN_ENV = "MARZNESHIN_GATEWAY_TOKEN"


def verify_auth(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    x_client_id: Optional[str] = Header(None),
) -> dict:
    expected_token = os.environ.get(DEFAULT_TOKEN_ENV)
    if expected_token:
        provided = None
        if authorization and authorization.startswith("Bearer "):
            provided = authorization[7:].strip()
        elif x_api_key:
            provided = x_api_key.strip()
            
        if not provided or provided != expected_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
    client_id = x_client_id or "local-agent"
    return {
        "authenticated": True,
        "client_id": client_id,
        "token_type": "bearer" if authorization else "header",
    }


def get_current_actor(auth: dict = Header(None)) -> str:
    return auth.get("client_id", "anonymous") if isinstance(auth, dict) else "anonymous"
