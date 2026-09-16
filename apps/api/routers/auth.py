"""Production auth routes (API_SPECIFICATION §3)."""

from __future__ import annotations

from fastapi import APIRouter

from apps.api.schemas import LoginRequest

router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.post("/auth/login")
def login(payload: LoginRequest) -> dict[str, object]:
    """Return a bearer token for a permitted demo user.

    The project keeps these routes deterministic and DB-free for unit tests; a
    real deployment will replace this with JWT issuance against the auth store.
    """
    email = payload.email.lower()
    if email != "admin@dtck.local" or payload.password != "admin123":
        return {"error": {"code": "invalid_credentials", "message": "invalid email or password"}}

    return {
        "access_token": "dtck-demo-token-admin",
        "refresh_token": "dtck-demo-refresh-admin",
        "token_type": "bearer",
        "expires_in": 3600,
        "user": {"email": email, "role": "ADMIN"},
    }


__all__ = ["router"]
