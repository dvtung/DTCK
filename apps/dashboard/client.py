"""Data client for the Streamlit dashboard (T011).

Tries the FastAPI service over HTTP first; if unreachable it falls back to
the in-process ``MarketService`` so the dashboard works offline (and in tests)
without a running API server.  When the persistence layer lands (KI-008), only
``MarketService`` is swapped for a SQLAlchemy repository — contracts are unchanged.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from apps.api.services.market_data import MarketService

DEFAULT_BASE = os.getenv("API_HOST", "http://localhost:8000")


class MarketClient:
    """Thin client over the DTCK FastAPI endpoints (or in-process fallback)."""

    def __init__(self, base_url: str = DEFAULT_BASE, timeout: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._svc = MarketService()

    # -- low-level transport ------------------------------------------------
    def _get(self, path: str, **params: Any) -> dict[str, Any] | list[Any]:
        """GET a JSON payload, falling back to the in-process service."""
        try:
            resp = httpx.get(f"{self.base_url}{path}", params=params or None, timeout=self._timeout)
            resp.raise_for_status()
            return resp.json()  # type: ignore[no-any-return]
        except (httpx.HTTPError, ValueError):
            # Offline fallback — strip the /api/v1 prefix and use in-process methods.
            key = path.removeprefix("/api/v1")
            return self._fallback(key, params)

    def _fallback(self, key: str, params: dict[str, Any]) -> dict[str, Any] | list[Any]:
        """Map path fragments to ``MarketService`` methods."""
        symbol = params.get("symbol")
        if key == "/market/indices":
            return self._svc.list_indices()
        if key == "/market/indices/{code}":
            return self._svc.get_index(params.get("code", "")) or {}
        if key == "/market/regime":
            return self._svc.get_regime()
        if key == "/market/breadth":
            return self._svc.get_breadth()
        if key == "/stocks":
            return self._svc.list_stocks(
                exchange=params.get("exchange"),
                sector=params.get("sector"),
                vn30=params.get("vn30"),
            )
        if key == "/stocks/rankings":
            return self._svc.get_ranked()
        if key == "/news":
            return self._svc.list_news()
        if key == "/backtests":
            return self._svc.list_backtests()
        if key.startswith("/backtests/"):
            tail = key.removeprefix("/backtests/")
            bt_id, slash, sub = tail.partition("/")
            if slash and sub == "metrics":
                return self._svc.get_backtest_metrics(bt_id)
            if slash and sub == "trades":
                return self._svc.get_backtest_trades(bt_id)
            if not slash:
                return self._svc.get_backtest(bt_id) or {}
        if not symbol:
            if key in ("/healthz", "/readyz"):
                return {"status": "ok", "service": "dashboard-fallback"}
            return {}
        if key == "/stocks/{symbol}":
            return self._svc.get_stock(symbol) or {}
        if key == "/stocks/{symbol}/prices":
            return self._svc.get_prices(symbol) or []
        if key == "/stocks/{symbol}/ranking":
            return self._svc.get_ranking(symbol) or {}
        if key == "/stocks/{symbol}/indicators":
            return self._svc.get_indicators(symbol) or {}
        if key == "/valuation/{symbol}/summary":
            return self._svc.get_valuation_summary(symbol) or {}
        if key == "/fundamentals/{symbol}/quality":
            return self._svc.get_quality(symbol) or {}
        if key == "/technical/{symbol}/indicators":
            return self._svc.get_indicators(symbol) or {}
        if key == "/news":
            return self._svc.list_news()
        if key == "/backtests":
            return self._svc.list_backtests()
        if key.startswith("/backtests/"):
            tail = key.removeprefix("/backtests/")
            bt_id, slash, sub = tail.partition("/")
            if slash and sub == "metrics":
                return self._svc.get_backtest_metrics(bt_id)
            if slash and sub == "trades":
                return self._svc.get_backtest_trades(bt_id)
            if not slash:
                return self._svc.get_backtest(bt_id) or {}
        if key in ("/healthz", "/readyz"):
            return {"status": "ok", "service": "dashboard-fallback"}
        raise KeyError(f"Unknown dashboard route: {key}")

    # -- high-level accessors ----------------------------------------------
    def get_indices(self) -> list[dict[str, Any]]:
        return self._get("/api/v1/market/indices")  # type: ignore[return-value]

    def get_regime(self) -> dict[str, Any]:
        return self._get("/api/v1/market/regime")  # type: ignore[return-value]

    def get_breadth(self) -> dict[str, Any]:
        return self._get("/api/v1/market/breadth")  # type: ignore[return-value]

    def list_stocks(self) -> list[dict[str, Any]]:
        return self._get("/api/v1/stocks")  # type: ignore[return-value]

    def get_ranked(self) -> list[dict[str, Any]]:
        return self._get("/api/v1/stocks/rankings")  # type: ignore[return-value]

    def get_stock(self, symbol: str) -> dict[str, Any]:
        return self._get("/api/v1/stocks/{symbol}", symbol=symbol)  # type: ignore[return-value]

    def get_prices(self, symbol: str) -> list[dict[str, Any]]:
        return self._get("/api/v1/stocks/{symbol}/prices", symbol=symbol)  # type: ignore[return-value]

    def get_ranking(self, symbol: str) -> dict[str, Any]:
        return self._get("/api/v1/stocks/{symbol}/ranking", symbol=symbol)  # type: ignore[return-value]

    def get_indicators(self, symbol: str) -> dict[str, Any]:
        return self._get("/api/v1/technical/{symbol}/indicators", symbol=symbol)  # type: ignore[return-value]

    def get_valuation(self, symbol: str) -> dict[str, Any]:
        return self._get("/api/v1/valuation/{symbol}/summary", symbol=symbol)  # type: ignore[return-value]

    def get_quality(self, symbol: str) -> dict[str, Any]:
        return self._get("/api/v1/fundamentals/{symbol}/quality", symbol=symbol)  # type: ignore[return-value]

    def get_news(self) -> list[dict[str, Any]]:
        return self._get("/api/v1/news")  # type: ignore[return-value]

    def get_backtests(self) -> list[dict[str, Any]]:
        return self._get("/api/v1/backtests")  # type: ignore[return-value]

    def get_backtest_metrics(self, bt_id: str) -> list[dict[str, Any]]:
        return self._get(f"/api/v1/backtests/{bt_id}/metrics")  # type: ignore[return-value]

    def get_backtest_trades(self, bt_id: str) -> list[dict[str, Any]]:
        return self._get(f"/api/v1/backtests/{bt_id}/trades")  # type: ignore[return-value]
    def get_backtest(self, bt_id: str) -> dict[str, Any]:
        return self._get(f"/api/v1/backtests/{bt_id}")  # type: ignore[return-value]
    def get_health(self) -> dict[str, Any]:

        return self._get("/healthz")  # type: ignore[return-value]
