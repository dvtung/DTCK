"""ASGI middleware: API-key auth for state-changing routes + HTTP metrics (T015).

Auth (spec §32 / ``docs/SECURITY_vi.md``): when ``API_AUTH_KEY`` is set, every
``POST``/``PUT``/``PATCH``/``DELETE`` under ``/api/v1/`` (except the login
endpoint itself) must carry ``Authorization: Bearer <key>``. Comparison uses
``secrets.compare_digest`` (constant time). With the key unset (the default,
and what unit tests use) the middleware is a no-op so offline demos keep
working — production deployments must set it.

Metrics (spec §46): every HTTP request is timed and labelled with the matched
route template (never the raw path, to bound cardinality).
"""

from __future__ import annotations

import secrets
import time
from collections.abc import Awaitable

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from apps.api import metrics

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# Login must stay open: it is how a caller obtains the first credential.
_AUTH_EXEMPT_PATHS = frozenset({"/api/v1/auth/login"})


def _unauthorized(send: Send) -> Awaitable[None]:
    """401 in the documented error envelope (§2.1)."""
    body = (
        b'{"error":{"code":"unauthorized",'
        b'"message":"missing or invalid API key (Authorization: Bearer <key>)"}}'
    )

    async def _send() -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"www-authenticate", b"Bearer"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    return _send()


class ApiKeyAuthMiddleware:
    """Bearer API-key gate for state-changing API routes (no-op without a key)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        from apps.api.config import settings

        required = (settings.api_auth_key or "").strip()
        if required:
            path = scope.get("path", "")
            method = scope.get("method", "GET")
            # /metrics exposes operational internals — gate it whenever a key
            # exists, even though scraping is a GET.
            needs_key = path == "/metrics" or (
                path.startswith("/api/v1/")
                and method not in _SAFE_METHODS
                and path not in _AUTH_EXEMPT_PATHS
            )
            if needs_key:
                auth_header = b""
                for name, value in scope.get("headers", []):
                    if name == b"authorization":
                        auth_header = value
                        break
                presented = auth_header[7:] if auth_header.startswith(b"Bearer ") else b""
                accepted = bool(presented) and self._is_valid_credential(presented)
                if not accepted:
                    await _unauthorized(send)
                    return

        await self.app(scope, receive, send)

    @staticmethod
    def _is_valid_credential(presented: bytes) -> bool:
        """Machine API key (constant-time) **or** a properly signed JWT.

        Both are checked here so a user JWT issued by /auth/login can reach the
        RBAC-guarded write routes when a machine key is also configured; a
        forged token fails the signature check at the middleware, before any
        route without a role dependency could see it (T015b).
        """
        from apps.api.config import settings
        from apps.api.security import decode_token

        machine_key = (settings.api_auth_key or "").strip()
        if machine_key and secrets.compare_digest(presented, machine_key.encode("utf-8")):
            return True
        if settings.auth_jwt_secret:
            try:
                decode_token(presented.decode("utf-8", errors="replace"))
                return True
            except ValueError:
                return False
        return False


class MetricsMiddleware:
    """Record request count + latency for every HTTP request (spec §46)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # ``route`` is populated by Starlette's router during dispatch.
            route = scope.get("route")
            route_label = getattr(route, "path", None) or scope.get("path", "unmatched")
            metrics.record_request(
                method=str(scope.get("method", "GET")),
                route=str(route_label),
                status=status_code,
                duration_seconds=time.perf_counter() - started,
            )


__all__ = ["ApiKeyAuthMiddleware", "MetricsMiddleware"]
