"""JWT issuance + role enforcement (spec §3/§32, T015b).

Paper-thin HS256 JWT built on the standard library (``hmac``/``hashlib``/
``base64``/``json``) — the project dependency policy requires explicit approval
for new packages, and the token shape we need (subject, role, expiry, signature)
does not justify one.

Two independent credentials are accepted on protected routes:

* the **machine** API key (``API_AUTH_KEY``, middleware-gated) → role ``ADMIN``;
* a **user** JWT minted by ``POST /api/v1/auth/login`` → the role in its claims.

With neither configured (offline demos, unit tests) the dependency resolves a
synthetic ``ADMIN`` identity so the documented single-process demo keeps working.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from apps.api.config import settings

__all__ = [
    "ADMIN",
    "ANALYST",
    "ROLES",
    "VIEWER",
    "create_token",
    "decode_token",
    "get_current_user",
    "require_roles",
]

ADMIN = "ADMIN"
ANALYST = "ANALYST"
VIEWER = "VIEWER"
ROLES = frozenset({ADMIN, ANALYST, VIEWER})

_ALGORITHM = "HS256"
_bearer = HTTPBearer(auto_error=False)


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign(message: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    return _b64url_encode(digest)


def create_token(
    subject: str,
    role: str = VIEWER,
    *,
    token_type: str = "access",
    ttl_seconds: int | None = None,
    now: int | None = None,
) -> str:
    """Mint a signed token (``token_type`` = ``access`` | ``refresh``)."""
    if role not in ROLES:
        raise ValueError(f"unknown role {role!r}; expected one of {sorted(ROLES)}")
    issued_at = int(now if now is not None else time.time())
    ttl = ttl_seconds if ttl_seconds is not None else settings.auth_jwt_ttl_seconds
    header = {"alg": _ALGORITHM, "typ": "JWT"}
    payload = {
        "sub": subject,
        "role": role,
        "type": token_type,
        "iat": issued_at,
        "exp": issued_at + int(ttl),
    }
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    return f"{header_b64}.{payload_b64}.{_sign(signing_input, settings.auth_jwt_secret)}"


def decode_token(token: str, *, now: int | None = None) -> dict[str, Any]:
    """Verify signature + expiry and return the claims.

    Raises ``ValueError`` on any structural, signature, or expiry problem — the
    caller maps it onto the documented 401 envelope.
    """
    if not settings.auth_jwt_secret:
        raise ValueError("auth_jwt_secret is not configured")
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("malformed token")
    header_b64, payload_b64, signature = parts
    expected = _sign(f"{header_b64}.{payload_b64}".encode("ascii"), settings.auth_jwt_secret)
    if not hmac.compare_digest(signature, expected):
        raise ValueError("invalid signature")
    try:
        claims = json.loads(_b64url_decode(payload_b64))
    except Exception as exc:  # noqa: BLE001 — any decode failure is a bad token
        raise ValueError("undecodable payload") from exc
    if not isinstance(claims, dict):
        raise ValueError("payload is not an object")
    expires_at = claims.get("exp")
    reference = int(now if now is not None else time.time())
    if not isinstance(expires_at, int) or expires_at <= reference:
        raise ValueError("token expired")
    return claims


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": "unauthorized", "message": message}},
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden(role: str, allowed: tuple[str, ...]) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": {
                "code": "forbidden",
                "message": f"role {role!r} cannot perform this action "
                f"(requires one of {list(allowed)})",
            }
        },
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict[str, Any]:
    """Resolve the caller identity, or raise 401.

    Order: machine API key → user JWT → offline demo identity (only when no
    credential mechanism is configured at all).
    """
    machine_key = (settings.api_auth_key or "").strip()
    jwt_configured = bool(settings.auth_jwt_secret)
    presented = credentials.credentials if credentials is not None else ""

    if machine_key and presented and hmac.compare_digest(presented, machine_key):
        return {"sub": "machine", "role": ADMIN, "via": "api_key"}
    if jwt_configured and presented:
        try:
            claims = decode_token(presented)
        except ValueError as exc:
            raise _unauthorized(str(exc)) from exc
        role = str(claims.get("role", VIEWER))
        if role not in ROLES:
            raise _unauthorized(f"unknown role {role!r}")
        return {"sub": str(claims.get("sub", "unknown")), "role": role, "via": "jwt"}
    if not machine_key and not jwt_configured:
        # Nothing is configured: keep the documented offline/demo behaviour.
        return {"sub": "demo", "role": ADMIN, "via": "offline"}
    raise _unauthorized("missing or invalid credentials")


def require_roles(*roles: str) -> Any:
    """Dependency factory: allow only the listed roles (401 → 403)."""
    allowed = tuple(roles)

    def _dependency(
        user: Annotated[dict[str, Any], Depends(get_current_user)],
    ) -> dict[str, Any]:
        if user.get("role") not in allowed:
            raise _forbidden(str(user.get("role")), allowed)
        return user

    return _dependency
