"""Unit tests for the strategy API router (GĐ 6)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apps.api.dependencies import get_strategy_service
from apps.api.main import app
from apps.api.services.strategy_service import NullStrategyService

FIXTURE_ROW: dict[str, Any] = {
    "symbol": "FPT",
    "company_name": "CTCP FPT",
    "strategy": "mid",
    "trade_date": date(2026, 10, 3),
    "overall_score": 72.5,
    "grade": "B",
    "group_scores": {"technical": 80.0, "quality": None},
    "buy_zone_low": 61000.0,
    "buy_zone_high": 62000.0,
    "stop_loss": 60000.0,
    "target_price": 65000.0,
    "rr_ratio": 1.5,
    "confidence": 0.7,
    "reasons": ["Nhóm 'technical' đóng góp 62% điểm"],
    "risks": [],
    "data_flags": {"missing_groups": ["quality"]},
    "scoring_version": "strategy_v1.0",
    "disclaimer": "Kết quả chỉ mang tính tham khảo.",
}


class _StubStrategyService(NullStrategyService):
    """Returns one fixture row; raises KeyError for an unknown profile."""

    def rankings(self, strategy: str, *, universe: str | None = None) -> list[dict[str, Any]]:
        if strategy not in ("short", "mid", "long"):
            raise KeyError(strategy)
        return [dict(FIXTURE_ROW, strategy=strategy)]

    def symbol_view(self, symbol: str) -> dict[str, Any] | None:
        if symbol != "FPT":
            return None
        return {
            "symbol": "FPT",
            "company_name": "CTCP FPT",
            "trade_date": date(2026, 10, 3),
            "profiles": [dict(FIXTURE_ROW)],
        }

    def history(self, symbol: str, strategy: str, *, limit: int = 60) -> list[dict[str, Any]]:
        if strategy not in ("short", "mid", "long"):
            raise KeyError(strategy)
        return [{"trade_date": date(2026, 10, 3), "overall_score": 72.5, "grade": "B"}]


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def stub_client() -> TestClient:
    app.dependency_overrides[get_strategy_service] = lambda: _StubStrategyService()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_strategy_service, None)


class TestMemoryMode:
    """With no database the endpoints answer honestly-empty, never fake data."""

    def test_rankings_are_empty(self, client: TestClient) -> None:
        response = client.get("/api/v1/strategy/rankings", params={"strategy": "mid"})
        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        assert body["total"] == 0

    def test_symbol_is_not_found(self, client: TestClient) -> None:
        assert client.get("/api/v1/strategy/FPT").status_code == 404


class TestRankingsEndpoint:
    def test_envelope_and_disclaimer(self, stub_client: TestClient) -> None:
        response = stub_client.get(
            "/api/v1/strategy/rankings", params={"strategy": "mid", "limit": 10}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        row = body["items"][0]
        assert row["symbol"] == "FPT"
        assert row["grade"] == "B"
        assert row["overall_score"] == 72.5
        assert row["rr_ratio"] == 1.5
        assert row["disclaimer"]  # §3 always present
        assert set(body) == {"items", "total", "limit", "offset"}

    def test_unknown_profile_is_422(self, stub_client: TestClient) -> None:
        response = stub_client.get(
            "/api/v1/strategy/rankings", params={"strategy": "swing"}
        )
        assert response.status_code == 422


class TestSymbolEndpoints:
    def test_symbol_view_lists_profiles(self, stub_client: TestClient) -> None:
        response = stub_client.get("/api/v1/strategy/FPT")
        assert response.status_code == 200
        body = response.json()
        assert body["symbol"] == "FPT"
        assert len(body["profiles"]) == 1
        assert body["profiles"][0]["disclaimer"]

    def test_unknown_symbol_is_404(self, stub_client: TestClient) -> None:
        assert stub_client.get("/api/v1/strategy/NOPE").status_code == 404

    def test_history_is_oldest_first(self, stub_client: TestClient) -> None:
        response = stub_client.get(
            "/api/v1/strategy/FPT/history", params={"strategy": "mid"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["strategy"] == "mid"
        assert body["items"][0]["grade"] == "B"

    def test_history_unknown_profile_is_422(self, stub_client: TestClient) -> None:
        response = stub_client.get(
            "/api/v1/strategy/FPT/history", params={"strategy": "swing"}
        )
        assert response.status_code == 422


class TestOpenApi:
    def test_routes_are_registered(self) -> None:
        paths = app.openapi()["paths"]
        assert "/api/v1/strategy/rankings" in paths
        assert "/api/v1/strategy/{symbol}" in paths
        assert "/api/v1/strategy/{symbol}/history" in paths
