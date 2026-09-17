"""Production auth routes (API_SPECIFICATION §3)."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, HTTPException, status

from apps.api.schemas import LoginRequest

router = APIRouter(prefix="/api/v1", tags=["auth"])

# Deterministic demo identity for the DB-free MVP (documented in SECURITY.md).
_DEMO_EMAIL = "admin@dtck.local"
_DEMO_PASSWORD = "admin123"


@router.post("/auth/login")
def login(payload: LoginRequest) -> dict[str, object]:
    """Return a bearer token for a permitted demo user; 401 otherwise.

    A real deployment replaces this with JWT issuance against the auth store —
    credentials then come from the environment, never from source (§32).
    """
    email_ok = secrets.compare_digest(payload.email.lower(), _DEMO_EMAIL)
    password_ok = secrets.compare_digest(payload.password, _DEMO_PASSWORD)
    if not (email_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "invalid_credentials",
                    "message": "invalid email or password",
                }
            },
        )

    return {
        "access_token": "dtck-demo-token-admin",
        "refresh_token": "dtck-demo-refresh-admin",
        "token_type": "bearer",
        "expires_in": 3600,
        "user": {"email": payload.email.lower(), "role": "ADMIN"},
    }


__all__ = ["router"]
