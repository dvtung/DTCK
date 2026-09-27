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

    def __init__(
        self,
        base_url: str = DEFAULT_BASE,
        timeout: float = 5.0,
        token: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout
        self.token = token
        self._svc = MarketService()
        # Which transport served the last call — surfaced in the dashboard so a
        # silent fixture fallback can never masquerade as real data (T015b).
        self.last_transport: str = "unknown"
        self.last_error: str = ""

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def login(self, email: str, password: str) -> dict[str, Any]:
        """Authenticate via POST /api/v1/auth/login and cache the JWT token."""
        try:
            resp = httpx.post(
                f"{self.base_url}/api/v1/auth/login",
                json={"email": email, "password": password},
                timeout=self._timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                self.token = str(data.get("access_token", ""))
                return {"success": True, "data": data}
            return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text}"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def source_badge(self) -> tuple[str, str]:
        """``("api", base_url)`` when the API answered, else ``("fixture", error)``."""
        if self.last_transport == "api":
            return "api", self.base_url
        return "fixture", self.last_error or "chưa kết nối"

    def probe(self) -> dict[str, Any]:
        """Hit ``/readyz`` directly to decide which transport is live."""
        try:
            resp = httpx.get(f"{self.base_url}/readyz", timeout=self._timeout)
            resp.raise_for_status()
            payload = resp.json()
            self.last_transport = "api"
            self.last_error = ""
            return payload if isinstance(payload, dict) else {}
        except (httpx.HTTPError, ValueError) as exc:
            self.last_transport = "fixture"
            self.last_error = str(exc)
            return {}

    # -- low-level transport ------------------------------------------------
    def _get(self, path: str, **params: Any) -> dict[str, Any] | list[Any]:
        """GET a JSON payload, falling back to the in-process service."""
        try:
            resp = httpx.get(
                f"{self.base_url}{path}",
                params=params or None,
                headers=self._headers(),
                timeout=self._timeout,
            )
            resp.raise_for_status()
            self.last_transport = "api"
            self.last_error = ""
            return resp.json()  # type: ignore[no-any-return]
        except (httpx.HTTPError, ValueError) as exc:
            # Offline fallback — strip the /api/v1 prefix and use in-process methods.
            self.last_transport = "fixture"
            self.last_error = str(exc)
            key = path.removeprefix("/api/v1")
            return self._fallback(key, params)

    def _fallback(self, key: str, params: dict[str, Any]) -> dict[str, Any] | list[Any]:
        """Map path fragments to ``MarketService`` methods."""
        symbol = params.get("symbol")
        # Concrete URLs (``/stocks/FPT/prices``) are normalised back to the
        # template form used below, so both callers work (T015c).
        if symbol:
            key = key.replace(str(symbol), "{symbol}")
        code = params.get("code")
        if code:
            key = key.replace(str(code), "{code}")
        if key == "/market/indices":
            return self._svc.list_indices()
        if key == "/market/indices/{code}/prices":
            return self._svc.get_index_prices(str(params.get("code", ""))) or []
        if key == "/market/indices/{code}":
            return self._svc.get_index(params.get("code", "")) or {}
        if key == "/market/regime":
            return self._svc.get_regime()
        if key == "/market/breadth":
            return self._svc.get_breadth()
        if key == "/market/movers":
            return self._svc.get_movers(
                universe=str(params.get("universe") or "VN100"),
                limit=int(params.get("limit") or 10),
            )
        if key == "/stocks":
            return self._svc.list_stocks(
                exchange=params.get("exchange"),
                sector=params.get("sector"),
                vn30=params.get("vn30"),
                vn100=params.get("vn100"),
            )
        if key == "/stocks/ranked":
            return self._svc.get_ranked()
        if key == "/news":
            return self._svc.list_news()
        if key == "/rag/search":
            from apps.api.services.rag_service import get_rag_service

            rag = get_rag_service()
            docs = rag.search(
                params.get("q", ""),
                top_k=int(params.get("top_k", 5)),
                symbol=params.get("symbol") or "",
                doc_type=params.get("doc_type") or "",
                source=params.get("source") or "",
            )
            items = rag.to_payload(docs)
            return {
                "query": params.get("q", ""),
                "items": items,
                "total": len(items),
                "model": rag.model_name,
            }
        if key == "/rag/status":
            from apps.api.services.rag_service import get_rag_service

            return get_rag_service().status()
        if key == "/evidence":
            from apps.api.services.rag_service import get_rag_service

            rag = get_rag_service()
            q = params.get("q", "")
            evs = rag.evidence_for(
                q,
                top_k=int(params.get("top_k", 5)),
                symbol=params.get("symbol") or "",
            )
            return {"query": q, "items": rag.evidence_payload(evs), "total": len(evs)}
        if key == "/notifications/recipients":
            return []
        if key == "/notifications/smtp":
            return {}
        if key == "/notifications/schedule":
            return {
                "morning_hour": 8,
                "morning_minute": 0,
                "afternoon_hour": 15,
                "afternoon_minute": 30,
                "days_of_week": "mon-fri",
                "is_enabled": True,
            }
        if key == "/notifications/logs":
            return []
        if key == "/notifications/preview-html":
            return {"html": "<h1>Preview fallback</h1>"}

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
        if not symbol:
            return {}
        if key == "/stocks/{symbol}":
            return self._svc.get_stock(symbol) or {}
        if key == "/stocks/{symbol}/prices":
            return self._svc.get_prices(symbol) or []
        if key == "/stocks/{symbol}/ranking":
            return self._svc.get_ranking(symbol) or {}
        if key == "/technical/{symbol}/indicators":
            return self._svc.get_indicators(symbol) or {}
        if key == "/valuation/{symbol}/summary":
            return self._svc.get_valuation_summary(symbol) or {}
        if key == "/fundamentals/{symbol}/quality":
            return self._svc.get_quality(symbol) or {}
        if key.startswith("/predictions/"):
            # Offline fallback: the in-memory service has no trained model.
            return {}
        raise KeyError(f"Unknown dashboard route: {key}")

    # -- high-level accessors ----------------------------------------------
    @staticmethod
    def _unwrap_items(data: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
        """Normalize either a raw list or a paginated `{items, total, ...}` envelope."""
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
            return data["items"]
        return []

    def get_indices(self) -> list[dict[str, Any]]:
        res = self._get("/api/v1/market/indices")
        return self._unwrap_items(res) if isinstance(res, (dict, list)) else []

    def get_regime(self) -> dict[str, Any]:
        return self._get("/api/v1/market/regime")  # type: ignore[return-value]

    def get_breadth(self) -> dict[str, Any]:
        return self._get("/api/v1/market/breadth")  # type: ignore[return-value]

    def get_index_prices(self, code: str = "VNINDEX") -> list[dict[str, Any]]:
        """Index daily OHLCV series for candlestick charts."""
        res = self._get(f"/api/v1/market/indices/{code}/prices", code=code)
        return self._unwrap_items(res) if isinstance(res, (dict, list)) else []

    def get_movers(self, universe: str = "VN100", limit: int = 10) -> dict[str, Any]:
        """Top gainers and decliners with MA20 / MA50 deviation metrics."""
        res = self._get("/api/v1/market/movers", universe=universe, limit=limit)
        return res if isinstance(res, dict) else {"gainers": [], "decliners": []}

    def list_stocks(
        self,
        exchange: str | None = None,
        sector: str | None = None,
        vn30: bool | None = None,
        vn100: bool | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Reference universe — ``limit`` defaults to 200 so the full VN100 fits."""
        params: dict[str, Any] = {"limit": limit}
        if exchange:
            params["exchange"] = exchange
        if sector:
            params["sector"] = sector
        if vn30 is not None:
            params["vn30"] = vn30
        if vn100 is not None:
            params["vn100"] = vn100
        res = self._get("/api/v1/stocks", **params)
        return self._unwrap_items(res)

    def get_ranked(self) -> list[dict[str, Any]]:
        res = self._get("/api/v1/stocks/ranked")
        return self._unwrap_items(res)

    def get_stock(self, symbol: str) -> dict[str, Any]:
        return self._get(f"/api/v1/stocks/{symbol}", symbol=symbol)  # type: ignore[return-value]

    def get_prices(self, symbol: str) -> list[dict[str, Any]]:
        res = self._get(f"/api/v1/stocks/{symbol}/prices", symbol=symbol)
        return self._unwrap_items(res)

    def get_ranking(self, symbol: str) -> dict[str, Any]:
        return self._get(f"/api/v1/stocks/{symbol}/ranking", symbol=symbol)  # type: ignore[return-value]

    def get_indicators(self, symbol: str) -> dict[str, Any]:
        return self._get(f"/api/v1/technical/{symbol}/indicators", symbol=symbol)  # type: ignore[return-value]

    def get_valuation(self, symbol: str) -> dict[str, Any]:
        return self._get(f"/api/v1/valuation/{symbol}/summary", symbol=symbol)  # type: ignore[return-value]

    def get_quality(self, symbol: str) -> dict[str, Any]:
        return self._get(f"/api/v1/fundamentals/{symbol}/quality", symbol=symbol)  # type: ignore[return-value]

    def get_prediction(self, symbol: str) -> dict[str, Any]:
        """ML prediction P(return > 0) from the trained model (spec §2.8/§26)."""
        res = self._get(f"/api/v1/predictions/{symbol}", symbol=symbol)
        return res if isinstance(res, dict) else {}

    def analyze_symbol(self, symbol: str) -> dict[str, Any]:
        """Run the AI Analysis Agent for structured thesis + catalysts + risks (§20.2/§23)."""
        try:
            resp = httpx.post(
                f"{self.base_url}/api/v1/agents/analyze",
                json={"symbol": symbol},
                headers=self._headers(),
                timeout=60.0,
            )
            if resp.status_code == 200:
                return resp.json().get("analysis", {})  # type: ignore[no-any-return]
            return {"error": f"HTTP {resp.status_code}: {resp.text}"}
        except Exception as exc:
            return {"error": str(exc)}

    def create_backtest(
        self,
        strategy_name: str,
        start_date: str,
        end_date: str,
        universe: str = "VN30",
        run_type: str = "walk-forward",
    ) -> dict[str, Any]:
        """Trigger an execution run via POST /api/v1/backtests (KI-008 write path)."""
        try:
            resp = httpx.post(
                f"{self.base_url}/api/v1/backtests",
                json={
                    "strategy_name": strategy_name,
                    "strategy_version": "1.0.0",
                    "universe": universe,
                    "start_date": start_date,
                    "end_date": end_date,
                    "run_type": run_type,
                },
                headers=self._headers(),
                timeout=30.0,
            )
            if resp.status_code in (200, 201):
                return resp.json()  # type: ignore[no-any-return]
            return {"error": f"HTTP {resp.status_code}: {resp.text}"}
        except Exception as exc:
            return {"error": str(exc)}

    def get_news(
        self,
        symbol: str | None = None,
        source: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if symbol:
            params["symbol"] = symbol
        if source:
            params["source"] = source
        res = self._get("/api/v1/news", **params)
        return self._unwrap_items(res)

    def search_rag(
        self,
        query: str,
        symbol: str | None = None,
        top_k: int = 5,
        source: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"q": query, "top_k": top_k}
        if symbol:
            params["symbol"] = symbol
        if source:
            params["source"] = source
        res = self._get("/api/v1/rag/search", **params)
        return res if isinstance(res, dict) else {"items": res, "total": len(res)}

    def get_rag_status(self) -> dict[str, Any]:
        res = self._get("/api/v1/rag/status")
        return res if isinstance(res, dict) else {}

    def get_evidence(
        self,
        query: str,
        symbol: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"q": query, "top_k": top_k}
        if symbol:
            params["symbol"] = symbol
        res = self._get("/api/v1/evidence", **params)
        return self._unwrap_items(res)

    def get_backtests(self) -> list[dict[str, Any]]:
        res = self._get("/api/v1/backtests")
        return self._unwrap_items(res)

    def get_backtest_metrics(self, bt_id: str) -> list[dict[str, Any]]:
        res = self._get(f"/api/v1/backtests/{bt_id}/metrics")
        return self._unwrap_items(res)

    def get_backtest_trades(self, bt_id: str) -> list[dict[str, Any]]:
        res = self._get(f"/api/v1/backtests/{bt_id}/trades")
        return self._unwrap_items(res)

    def get_backtest(self, bt_id: str) -> dict[str, Any]:
        return self._get(f"/api/v1/backtests/{bt_id}")  # type: ignore[return-value]

    def get_health(self) -> dict[str, Any]:
        return self._get("/healthz")  # type: ignore[return-value]

    def get_metrics_text(self) -> str:
        """Fetch raw Prometheus /metrics text representation."""
        try:
            resp = httpx.get(f"{self.base_url}/metrics", timeout=self._timeout)
            if resp.status_code == 200:
                return resp.text
            return ""
        except Exception:
            return ""

    # --- Email notifications ---
    def get_email_recipients(self) -> list[dict[str, Any]]:
        res = self._get("/api/v1/notifications/recipients")
        return self._unwrap_items(res) if isinstance(res, (dict, list)) else []

    def add_email_recipient(self, email: str, name: str | None = None) -> dict[str, Any]:
        try:
            resp = httpx.post(
                f"{self.base_url}/api/v1/notifications/recipients",
                json={"email": email, "name": name},
                headers=self._headers(),
                timeout=self._timeout,
            )
            return resp.json() if resp.status_code in (200, 201) else {"error": resp.text}
        except Exception as exc:
            return {"error": str(exc)}

    def delete_email_recipient(self, recipient_id: str) -> dict[str, Any]:
        try:
            resp = httpx.delete(
                f"{self.base_url}/api/v1/notifications/recipients/{recipient_id}",
                headers=self._headers(),
                timeout=self._timeout,
            )
            return resp.json() if resp.status_code == 200 else {"error": resp.text}
        except Exception as exc:
            return {"error": str(exc)}

    def get_email_smtp(self) -> dict[str, Any]:
        res = self._get("/api/v1/notifications/smtp")
        return res if isinstance(res, dict) else {}

    def save_email_smtp(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = httpx.post(
                f"{self.base_url}/api/v1/notifications/smtp",
                json=payload,
                headers=self._headers(),
                timeout=self._timeout,
            )
            return resp.json() if resp.status_code == 200 else {"error": resp.text}
        except Exception as exc:
            return {"error": str(exc)}

    def get_email_schedule(self) -> dict[str, Any]:
        res = self._get("/api/v1/notifications/schedule")
        return res if isinstance(res, dict) else {}

    def save_email_schedule(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = httpx.post(
                f"{self.base_url}/api/v1/notifications/schedule",
                json=payload,
                headers=self._headers(),
                timeout=self._timeout,
            )
            return resp.json() if resp.status_code == 200 else {"error": resp.text}
        except Exception as exc:
            return {"error": str(exc)}

    def send_test_email(self, recipient_email: str) -> dict[str, Any]:
        try:
            resp = httpx.post(
                f"{self.base_url}/api/v1/notifications/send-test",
                json={"recipient_email": recipient_email},
                headers=self._headers(),
                timeout=30.0,
            )
            return resp.json() if resp.status_code == 200 else {"error": resp.text}
        except Exception as exc:
            return {"error": str(exc)}

    def get_email_preview_html(self) -> str:
        res = self._get("/api/v1/notifications/preview-html")
        return res.get("html", "") if isinstance(res, dict) else ""

    def get_email_logs(self) -> list[dict[str, Any]]:
        res = self._get("/api/v1/notifications/logs")
        return self._unwrap_items(res) if isinstance(res, (dict, list)) else []
