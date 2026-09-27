"""T015b tests — JWT issuance/verification + RBAC on write routes (spec §3/§32)."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from apps.api.config import settings
from apps.api.main import app
from apps.api.security import create_token, decode_token

client = TestClient(app)

_BACKTEST = {
    "strategy_name": "momentum_breakout_v1",
    "start_date": "2025-01-01",
    "end_date": "2026-01-01",
}


class TestTokenPrimitives:
    @pytest.fixture(autouse=True)
    def _secret(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "auth_jwt_secret", "unit-test-secret")

    def test_roundtrip_carries_subject_and_role(self) -> None:
        token = create_token("analyst@dtck.local", "ANALYST")
        claims = decode_token(token)
        assert claims["sub"] == "analyst@dtck.local"
        assert claims["role"] == "ANALYST"
        assert claims["type"] == "access"

    def test_token_is_three_base64url_segments(self) -> None:
        assert len(create_token("demo@dtck.local", "VIEWER").split(".")) == 3

    def test_tampered_signature_is_rejected(self) -> None:
        header, payload, _ = create_token("demo@dtck.local", "ADMIN").split(".")
        with pytest.raises(ValueError, match="invalid signature"):
            decode_token(f"{header}.{payload}.deadbeef")

    def test_tampered_payload_is_rejected(self) -> None:
        """Privilege escalation by editing the payload must break the signature."""
        token = create_token("viewer@dtck.local", "VIEWER")
        header, payload, signature = token.split(".")
        forged = create_token("viewer@dtck.local", "ADMIN").split(".")[1]
        with pytest.raises(ValueError, match="invalid signature"):
            decode_token(f"{header}.{forged}.{signature}")

    def test_expired_token_is_rejected(self) -> None:
        token = create_token("demo@dtck.local", "ADMIN", ttl_seconds=10, now=1_000_000)
        with pytest.raises(ValueError, match="token expired"):
            decode_token(token, now=1_000_020)

    def test_malformed_token_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="malformed token"):
            decode_token("not-a-jwt")

    def test_unknown_role_cannot_be_minted(self) -> None:
        with pytest.raises(ValueError, match="unknown role"):
            create_token("demo@dtck.local", "SUPERUSER")

    def test_missing_secret_fails_closed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "auth_jwt_secret", "")
        with pytest.raises(ValueError, match="not configured"):
            decode_token("a.b.c")


class TestRbacOnWriteRoutes:
    @pytest.fixture(autouse=True)
    def _auth(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "auth_jwt_secret", "unit-test-secret")
        monkeypatch.setattr(settings, "api_auth_key", "")

    def test_post_without_token_is_401(self) -> None:
        r = client.post("/api/v1/backtests", json=_BACKTEST)
        assert r.status_code == 401
        assert r.json()["detail"]["error"]["code"] == "unauthorized"

    def test_viewer_cannot_create_a_run(self) -> None:
        token = create_token("viewer@dtck.local", "VIEWER")
        r = client.post(
            "/api/v1/backtests", json=_BACKTEST, headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 403
        assert r.json()["detail"]["error"]["code"] == "forbidden"

    def test_analyst_can_create_a_run(self) -> None:
        token = create_token("analyst@dtck.local", "ANALYST")
        r = client.post(
            "/api/v1/backtests", json=_BACKTEST, headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 201
        assert r.json()["created"] is True

    def test_admin_can_create_a_run(self) -> None:
        token = create_token("admin@dtck.local", "ADMIN")
        r = client.post(
            "/api/v1/backtests", json=_BACKTEST, headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 201

    def test_reads_stay_open(self) -> None:
        assert client.get("/api/v1/backtests").status_code == 200

    def test_machine_api_key_is_accepted_as_admin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "api_auth_key", "machine-key")
        r = client.post(
            "/api/v1/backtests", json=_BACKTEST, headers={"Authorization": "Bearer machine-key"}
        )
        assert r.status_code == 201

    def test_login_issues_a_verifiable_jwt(self) -> None:
        r = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@dtck.local", "password": "admin123"},
        )
        assert r.status_code == 200
        body = r.json()
        claims = decode_token(body["access_token"])
        assert claims["role"] == "ADMIN"
        assert claims["sub"] == "admin@dtck.local"
        # Refresh token is longer-lived and typed as such.
        refresh = decode_token(body["refresh_token"])
        assert refresh["type"] == "refresh"
        assert refresh["exp"] > claims["exp"]

    def test_login_keeps_demo_tokens_without_a_secret(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "auth_jwt_secret", "")
        r = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@dtck.local", "password": "admin123"},
        )
        assert r.status_code == 200
        assert r.json()["access_token"] == "dtck-demo-token-admin"


def test_offline_mode_permits_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    """No key and no secret configured → documented demo identity still works."""
    monkeypatch.setattr(settings, "auth_jwt_secret", "")
    monkeypatch.setattr(settings, "api_auth_key", "")
    assert client.post("/api/v1/backtests", json=_BACKTEST).status_code == 201


class TestMiddlewareCredentialGate:
    """When both credentials are configured, either one opens the write gate."""

    @pytest.fixture(autouse=True)
    def _both(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "auth_jwt_secret", "unit-test-secret")
        monkeypatch.setattr(settings, "api_auth_key", "machine-key")

    def test_user_jwt_passes_the_middleware_gate(self) -> None:
        token = create_token("analyst@dtck.local", "ANALYST")
        r = client.post(
            "/api/v1/backtests", json=_BACKTEST, headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 201

    def test_forged_jwt_is_rejected_before_the_route(self) -> None:
        header, payload, _ = create_token("admin@dtck.local", "ADMIN").split(".")
        r = client.post(
            "/api/v1/backtests",
            json=_BACKTEST,
            headers={"Authorization": f"Bearer {header}.{payload}.forged"},
        )
        assert r.status_code == 401

    def test_machine_key_still_works(self) -> None:
        r = client.post(
            "/api/v1/backtests",
            json=_BACKTEST,
            headers={"Authorization": "Bearer machine-key"},
        )
        assert r.status_code == 201

    def test_junk_is_rejected(self) -> None:
        r = client.post(
            "/api/v1/backtests",
            json=_BACKTEST,
            headers={"Authorization": "Bearer whatever"},
        )
        assert r.status_code == 401


def test_expiry_uses_wall_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sanity: a token minted now is still valid a second later."""
    monkeypatch.setattr(settings, "auth_jwt_secret", "unit-test-secret")
    token = create_token("demo@dtck.local", "ADMIN")
    assert decode_token(token, now=int(time.time()))["role"] == "ADMIN"
