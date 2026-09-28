"""T010 tests — FastAPI /api/v1 read paths (docs/API_SPECIFICATION.md).

Covers: health/readiness, market/stocks/fundamentals/technical/valuation/news/
backtests groups, pagination convention, and the 404 error envelope.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


class TestSystem:
    def test_healthz(self) -> None:
        r = client.get("/healthz")
        assert r.status_code == 200
        assert r.json() == {"status": "ok", "service": "api", "version": "0.1.0"}

    def test_readyz(self) -> None:
        r = client.get("/readyz")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ready"
        assert set(body["dependencies"]) == {"database", "qdrant", "agents", "models"}
        # Dependencies are probed, not hardcoded — a fresh clone (no DB, no
        # qdrant_client) must still answer 200 with honest statuses.
        assert body["dependencies"]["database"] in (
            "connected",
            "connected-no-prices",
            "unreachable",
        )
        assert body["dependencies"]["qdrant"] in ("up", "offline-index-ready")
        assert body["market_source"].startswith(("memory", "auto", "db"))

    def test_readyz_database_probe_is_not_hardcoded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """KI-008: `database` reflects a real probe (was hardcoded "pending")."""
        from apps.api import db as api_db
        from apps.api import main as api_main

        monkeypatch.setattr(api_db, "database_is_ready", lambda **_: False)
        assert api_main._database_status() == "unreachable"  # noqa: SLF001

        calls: list[bool] = []

        def fake(require_prices: bool = True) -> bool:
            calls.append(require_prices)
            return require_prices is False  # socket ok, `prices` empty

        monkeypatch.setattr(api_db, "database_is_ready", fake)
        assert api_main._database_status() == "connected-no-prices"  # noqa: SLF001
        assert calls == [False, True]

    def test_readyz_market_source_reports_the_service_in_use(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """KI-008: `market_source` shows the mode *and* the service serving reads."""
        from apps.api import dependencies
        from apps.api import main as api_main
        from apps.api.services.db_market import DbMarketService
        from apps.api.services.market_data import MarketService

        monkeypatch.setattr(api_main.settings, "market_data_source", "auto")

        monkeypatch.setattr(dependencies, "get_market_service", lambda: MarketService())
        assert api_main._market_source_status() == "auto->memory"  # noqa: SLF001

        monkeypatch.setattr(dependencies, "get_market_service", DbMarketService)
        assert api_main._market_source_status() == "auto->db"  # noqa: SLF001

    def test_readyz_agents_reports_the_llm_model_when_wired(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from apps.api import main as api_main
        from apps.api.services import agent_service

        monkeypatch.setattr(agent_service, "get_llm_client", lambda: None)
        assert api_main._agents_status().startswith("offline:")  # noqa: SLF001

        class _FakeLLM:
            model = "qwen3.5"

        monkeypatch.setattr(agent_service, "get_llm_client", lambda: _FakeLLM())
        assert api_main._agents_status() == "llm:qwen3.5"  # noqa: SLF001


# ------------------------------------------------------------ market
def test_market_indices() -> None:
    r = client.get("/api/v1/market/indices")
    assert r.status_code == 200
    rows = r.json()
    assert {row["index_code"] for row in rows} >= {"VNINDEX", "VN30"}


def test_market_regime() -> None:
    r = client.get("/api/v1/market/regime")
    assert r.status_code == 200
    body = r.json()
    assert body["regime"] in ("BULL", "BEAR", "SIDEWAYS", "VOLATILE")


def test_market_breadth() -> None:
    r = client.get("/api/v1/market/breadth")
    assert r.status_code == 200
    assert r.json()["advancers"] + r.json()["decliners"] > 0


def test_market_index_prices_series() -> None:
    """T016: full OHLCV history for the candlestick chart (oldest first)."""
    r = client.get("/api/v1/market/indices/VNINDEX/prices")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) > 10
    dates = [row["trade_date"] for row in rows]
    assert dates == sorted(dates)
    assert {"open", "high", "low", "close", "volume"} <= set(rows[0])


def test_market_index_prices_unknown_index_404() -> None:
    r = client.get("/api/v1/market/indices/NOPE/prices")
    assert r.status_code == 404


def test_market_movers_top_gainers_decliners() -> None:
    """T016: top-10 gainers/decliners carry 1D change + MA20/MA50 distance."""
    r = client.get("/api/v1/market/movers", params={"universe": "VN100", "limit": 5})
    assert r.status_code == 200
    body = r.json()
    gainers, decliners = body["gainers"], body["decliners"]
    assert len(gainers) <= 5 and len(decliners) <= 5
    assert gainers and decliners
    # Ordered: gainers descending, decliners ascending by 1D change.
    g_chg = [g["change_pct"] for g in gainers]
    d_chg = [d["change_pct"] for d in decliners]
    assert g_chg == sorted(g_chg, reverse=True)
    assert d_chg == sorted(d_chg)
    for item in gainers + decliners:
        assert {"symbol", "close", "change_pct", "price_vs_sma20", "price_vs_sma50"} <= set(item)


def test_market_movers_unknown_universe_returns_empty_lists() -> None:
    r = client.get("/api/v1/market/movers", params={"universe": "NOSUCHINDEX"})
    assert r.status_code == 200
    assert r.json()["gainers"] == [] and r.json()["decliners"] == []


# ------------------------------------------------------------ stocks
def test_list_stocks_paginated() -> None:
    r = client.get("/api/v1/stocks", params={"limit": 3, "offset": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 7
    assert body["limit"] == 3 and body["offset"] == 2
    assert len(body["items"]) == 3


def test_stock_detail_and_prices() -> None:
    r = client.get("/api/v1/stocks/FPT")
    assert r.status_code == 200
    assert r.json()["symbol"] == "FPT"
    r = client.get("/api/v1/stocks/FPT/prices")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) > 0
    assert rows[0]["trade_date"] <= rows[-1]["trade_date"]


def test_stock_ranking_and_ranked() -> None:
    r = client.get("/api/v1/stocks/FPT/ranking")
    assert r.status_code == 200
    body = r.json()
    assert body["symbol"] == "FPT"
    assert 1 <= body["rank"] <= body["total"]
    r = client.get("/api/v1/stocks/ranked")
    assert r.status_code == 200
    ranked = r.json()
    scores = [row["overall_score"] for row in ranked if row["overall_score"] is not None]
    assert scores == sorted(scores, reverse=True)


def test_unknown_symbol_404_envelope() -> None:
    r = client.get("/api/v1/stocks/NOPE")
    assert r.status_code == 404
    body = r.json()
    assert "error" in body["detail"]
    assert body["detail"]["error"]["code"] == "not_found"


# --------------------------------------- fundamentals / technical / val
def test_fundamentals_quality() -> None:
    r = client.get("/api/v1/fundamentals/FPT/quality")
    assert r.status_code == 200
    assert r.json()["symbol"] == "FPT"


def test_technical_indicators() -> None:
    r = client.get("/api/v1/technical/FPT/indicators")
    assert r.status_code == 200
    # §2.4 promises the full set (RSI, MACD, MA, Bollinger, ATR…) — the read
    # path used to publish only 3 scalars (T015c).
    assert {
        "sma20",
        "sma50",
        "ema12",
        "ema26",
        "rsi14",
        "macd",
        "macd_signal",
        "bb_upper",
        "bb_lower",
        "atr14",
        "volume_sma20",
    } <= set(r.json()["series"])


def test_valuation_summary() -> None:
    r = client.get("/api/v1/valuation/FPT/summary")
    assert r.status_code == 200
    assert r.json()["pe"] is not None


# --------------------------------------------------------------- news
def test_news_pagination() -> None:
    r = client.get("/api/v1/news", params={"limit": 2, "offset": 1})
    assert r.status_code == 200
    assert r.json()["total"] == 3
    assert [row["id"] for row in r.json()["items"]] == [2, 1]


# ----------------------------------------------------------- backtests
def test_backtests_group() -> None:
    r = client.get("/api/v1/backtests")
    assert r.status_code == 200
    assert r.json()["total"] == 1
    r = client.get("/api/v1/backtests/bt-001")
    assert r.status_code == 200
    assert r.json()["strategy_name"] == "baseline_multi_factor"
    r = client.get("/api/v1/backtests/bt-001/metrics")
    assert r.status_code == 200
    assert {m["metric_name"] for m in r.json()} >= {"sharpe_ratio", "max_drawdown"}
    r = client.get("/api/v1/backtests/bt-001/trades")
    assert r.status_code == 200
    assert len(r.json()) == 2
    r = client.get("/api/v1/backtests/nope/metrics")
    assert r.status_code == 404


# --------------------------------------------------------------- rag/evidence (T012)
def test_rag_search() -> None:
    r = client.get("/api/v1/rag/search", params={"q": "FPT lợi nhuận", "top_k": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "FPT lợi nhuận"
    assert body["total"] >= 1
    assert "scores" in body["items"][0]


def test_rag_status() -> None:
    r = client.get("/api/v1/rag/status")
    assert r.status_code == 200
    body = r.json()
    assert body["chunks"] >= 1 and "model" in body


def test_evidence_list() -> None:
    r = client.get("/api/v1/evidence", params={"q": "FPT", "top_k": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert "confidence" in body["items"][0]


# --------------------------------------------------------------- agents (T013)
def test_agents_registry() -> None:
    r = client.get("/api/v1/agents")
    assert r.status_code == 200
    body = r.json()
    assert {a["agent_id"] for a in body["agents"]} == {
        "analysis",
        "research",
        "monitoring",
        "portfolio",
    }
    assert "get_stock_price" in body["tools"]
    assert body["model"] == "deterministic-quant-v1"


def test_agent_analyze_and_audit_trail() -> None:
    r = client.post("/api/v1/agents/analyze", json={"symbol": "FPT"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "succeeded"
    assert body["analysis"]["symbol"] == "FPT"
    assert body["analysis"]["thesis"]
    assert body["analysis"]["confidence"] > 0

    run_id = body["agent_run_id"]
    r = client.get(f"/api/v1/agents/runs/{run_id}")
    assert r.status_code == 200
    run = r.json()
    assert run["agent_id"] == "analysis"
    assert run["plan"] and run["tools_called"] and run["finished_at"]

    r = client.get("/api/v1/agents/runs", params={"agent_id": "analysis", "limit": 5})
    assert r.status_code == 200
    assert r.json()["total"] >= 1

    r = client.get("/api/v1/agents/runs/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_agent_analyze_unknown_symbol() -> None:
    r = client.post("/api/v1/agents/analyze", json={"symbol": "NOPE"})
    assert r.status_code == 404
    assert r.json()["detail"]["error"]["code"] == "not_found"
    r = client.post("/api/v1/agents/analyze", json={})
    assert r.status_code == 422


def test_agent_research_monitor_portfolio() -> None:
    r = client.post("/api/v1/agents/research", json={"symbol": "VCB"})
    assert r.status_code == 200
    assert r.json()["brief"]["key_facts"]
    r = client.post("/api/v1/agents/monitor", json={"symbols": ["FPT", "VCB"]})
    assert r.status_code == 200
    assert r.json()["report"]["alerts"]
    r = client.post(
        "/api/v1/agents/portfolio",
        json={"positions": [{"symbol": "FPT", "quantity": 100}]},
    )
    assert r.status_code == 200
    assert r.json()["snapshot"]["positions"] == 1


def test_analysis_async_pattern() -> None:
    r = client.post("/api/v1/analysis/request", json={"symbol": "VNM"})
    assert r.status_code == 202
    run_id = r.json()["agent_run_id"]
    r = client.get(f"/api/v1/analysis/request/{run_id}")
    assert r.status_code == 200
    assert r.json()["status"] == "succeeded"
    assert r.json()["analysis"]["symbol"] == "VNM"

    r = client.get("/api/v1/analysis/VNM/latest")
    assert r.status_code == 200
    assert r.json()["confidence"] > 0
    assert client.get("/api/v1/analysis/NOPE/latest").status_code == 404
    r = client.get("/api/v1/analysis/request/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_readyz_reports_agents() -> None:
    """`agents` names the reasoning layer that would serve a run (T016)."""
    body = client.get("/readyz").json()
    agents = body["dependencies"]["agents"]
    assert agents.startswith(("offline:", "llm:")), agents


def test_readyz_reports_models() -> None:
    """`models` names the serving model or the honest `stub` (T015b)."""
    body = client.get("/readyz").json()
    models = body["dependencies"]["models"]
    assert models in ("stub", "unavailable") or "@1.0.0" in models, models


def test_auth_rejects_bad_credentials_with_401() -> None:
    """Invalid credentials are an auth failure (401), not a 200 with an error body."""
    r = client.post(
        "/api/v1/auth/login", json={"email": "nobody@dtck.local", "password": "wrong"}
    )
    assert r.status_code == 401
    assert r.json()["detail"]["error"]["code"] == "invalid_credentials"


def test_auth_wrong_password_for_known_email_is_401() -> None:
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@dtck.local", "password": "not-admin123"},
    )
    assert r.status_code == 401




# ------------------------------------------------------------ notifications (T018)
def test_notifications_read_endpoints_open() -> None:
    """Read endpoints for schedule/smtp/logs answer 200 without credentials."""
    for path in (
        "/api/v1/notifications/recipients",
        "/api/v1/notifications/schedule",
        "/api/v1/notifications/smtp",
        "/api/v1/notifications/logs",
        "/api/v1/notifications/preview-html",
    ):
        r = client.get(path)
        assert r.status_code == 200, f"{path} returned {r.status_code}"


def test_notifications_preview_html_returns_rendered_content() -> None:
    r = client.get("/api/v1/notifications/preview-html")
    assert r.status_code == 200
    html = r.json().get("html", "")
    assert "<!DOCTYPE html>" in html
    assert "DTCK" in html


def test_notifications_schedule_exposes_three_report_windows() -> None:
    """The schedule contract carries the 08:00 / 12:30 / 16:30 windows."""
    payload = {
        "morning_hour": 8,
        "morning_minute": 0,
        "noon_hour": 12,
        "noon_minute": 30,
        "afternoon_hour": 16,
        "afternoon_minute": 30,
        "days_of_week": "mon-fri",
        "is_enabled": True,
    }
    r = client.post("/api/v1/notifications/schedule", json=payload)
    assert r.status_code == 200, r.text
    assert r.json().get("success") is True

    saved = client.get("/api/v1/notifications/schedule")
    assert saved.status_code == 200
    body = saved.json()
    for key, value in payload.items():
        assert body.get(key) == value, f"{key} round-trip mismatch"


def test_notifications_schedule_rejects_out_of_range_hour() -> None:
    r = client.post(
        "/api/v1/notifications/schedule",
        json={"noon_hour": 24, "noon_minute": 30},
    )
    assert r.status_code == 422


def test_notifications_invalid_email_returns_422() -> None:
    r = client.post(
        "/api/v1/notifications/recipients",
        json={"email": "not-an-email"},
    )
    assert r.status_code == 422


def test_notifications_send_test_offline_graceful_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without SMTP config, send-test reports an honest error without crashing.

    ``get_mailer`` is forced to ``None`` so the assertion stays deterministic even
    when a developer machine has a real SMTP configuration saved in the database.
    """
    from src.notifications.service import NotificationService

    monkeypatch.setattr(NotificationService, "get_mailer", lambda self: None)
    r = client.post(
        "/api/v1/notifications/send-test",
        json={"recipient_email": "test@example.com"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is False
    assert "SMTP" in body.get("error", "") or "Cấu hình" in body.get("error", "")

