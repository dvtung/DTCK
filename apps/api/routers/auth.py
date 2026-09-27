"""Production auth routes (API_SPECIFICATION §3)."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, HTTPException, status

from apps.api.schemas import LoginRequest

router = APIRouter(prefix="/api/v1", tags=["auth"])

# Deterministic demo identity for the DB-free MVP (documented in SECURITY.md).
_DEMO_EMAIL = "admin@dtck.local"
_DEMO_PASSWORD = "admin123"
_DEMO_ROLE = "ADMIN"


@router.post("/auth/login")
def login(payload: LoginRequest) -> dict[str, object]:
    """Return a bearer token for a permitted demo user; 401 otherwise.

    With ``AUTH_JWT_SECRET`` configured the tokens are signed HS256 JWTs
    carrying the user role (T015b); without it the deterministic demo strings
    are kept so offline runs and unit tests need no secret.  A real deployment
    replaces the demo identity with the ``users`` table (§16.1).
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

    email = payload.email.lower()
    role = _DEMO_ROLE
    from apps.api.config import settings

    if settings.auth_jwt_secret:
        from apps.api.security import create_token

        access_token = create_token(email, role, token_type="access")
        refresh_token = create_token(
            email,
            role,
            token_type="refresh",
            ttl_seconds=settings.auth_refresh_ttl_seconds,
        )
    else:
        access_token = "dtck-demo-token-admin"
        refresh_token = "dtck-demo-refresh-admin"

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.auth_jwt_ttl_seconds,
        "user": {"email": email, "role": role},
    }


__all__ = ["router"]
