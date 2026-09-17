"""T010 tests — FastAPI /api/v1 read paths (docs/API_SPECIFICATION.md).

Covers: health/readiness, market/stocks/fundamentals/technical/valuation/news/
backtests groups, pagination convention, and the 404 error envelope.
"""

from __future__ import annotations

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
        assert "dependencies" in r.json()


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
    assert set(r.json()["series"]) == {"sma20", "ema12", "rsi14"}


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
    body = client.get("/readyz").json()
    assert body["dependencies"]["agents"].startswith("offline:")
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

