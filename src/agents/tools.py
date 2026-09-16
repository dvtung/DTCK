"""Agent tool catalog (§22).

Tools are the ONLY way agents touch application services.  They wrap the
in-memory ``MarketService`` and ``RagService`` and return structured dicts.
Agents never access the database directly and never compute indicators
themselves (§22/§47) — every number comes back from the quant engine or the
RAG evidence pipeline.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from time import perf_counter
from typing import TYPE_CHECKING, Any

from src.agents.schemas import AgentToolCallRecord
from src.agents.util import round_score
from src.market.risk import risk as risk_engine
from src.ml.feature_dataset import MarketLike
from src.ml.predictor import PredictionService

if TYPE_CHECKING:
    from src.rag.service import RagService

# Catalog: §22 lists get_stock_price, get_technical, get_fundamentals,
# get_valuation, get_peer_analysis, get_market_regime, get_news,
# get_corporate_events, get_prediction, get_risk.  get_stock_profile,
# get_ranking and search_evidence expose the scoring engine + RAG pipeline.
Recorder = Callable[[AgentToolCallRecord], None]


def _num(value: Any, default: float = 0.0) -> float:
    """Coerce a service value to float, falling back to ``default``."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _mapping(value: Any) -> dict[str, Any]:
    """Narrow a service value to ``dict[str, Any]`` (empty when not a mapping)."""
    return dict(value) if isinstance(value, dict) else {}


class ToolCatalog:
    """Deterministic tool registry bound to the app services."""

    def __init__(
        self,
        market: MarketLike,
        rag: RagService,
        *,
        recorder: Recorder | None = None,
    ) -> None:
        self._market = market
        self._rag = rag
        self._recorder = recorder

    # ------------------------------------------------------------- market
    def get_market_regime(self) -> dict[str, Any]:
        row = self._market.get_regime()
        return {
            "available": True,
            "regime": str(row.get("regime", "UNKNOWN")),
            "confidence": round_score(row.get("confidence"), 4),
            "trade_date": str(row.get("trade_date")),
        }

    # -------------------------------------------------------------- stock
    def get_stock_profile(self, symbol: str) -> dict[str, Any]:
        stock = self._market.get_stock(symbol)
        if not stock:
            return {"symbol": symbol, "available": False}
        return {
            "symbol": symbol,
            "available": True,
            "company_name": str(stock.get("company_name", "")),
            "exchange": str(stock.get("exchange", "")),
            "sector": str(stock.get("sector", "")),
            "industry": str(stock.get("industry", "")),
            "status": str(stock.get("status", "")),
            "is_vn30": bool(stock.get("is_vn30")),
        }

    def get_stock_price(self, symbol: str) -> dict[str, Any]:
        rows = self._market.get_prices(symbol)
        if not rows:
            return {"symbol": symbol, "available": False}
        last = rows[-1]
        prev = rows[-2] if len(rows) > 1 else last
        window = rows[-20:]
        highs = [_num(r.get("high")) for r in window]
        lows = [_num(r.get("low")) for r in window]
        volumes = [_num(r.get("volume")) for r in window]
        close = _num(last.get("close"))
        prev_close = _num(prev.get("close"))
        change_pct = (close - prev_close) / prev_close if prev_close else 0.0
        return {
            "symbol": symbol,
            "available": True,
            "trade_date": str(last.get("trade_date")),
            "price": round(close, 2),
            "change_pct": round(change_pct, 4),
            "volume": int(_num(last.get("volume"))),
            "high_20": round(max(highs), 2) if highs else None,
            "low_20": round(min(lows), 2) if lows else None,
            "volume_avg_20": round(sum(volumes) / len(volumes), 2) if volumes else None,
        }

    def get_technical(self, symbol: str) -> dict[str, Any]:
        row = self._market.get_indicators(symbol)
        if not row:
            return {"symbol": symbol, "available": False}
        series = _mapping(row.get("series"))
        return {
            "symbol": symbol,
            "available": True,
            "as_of": str(row.get("as_of")),
            "series": {str(k): None if v is None else round(_num(v), 4) for k, v in series.items()},
        }

    def get_fundamentals(self, symbol: str) -> dict[str, Any]:
        row = self._market.get_quality(symbol)
        if not row:
            return {"symbol": symbol, "available": False}
        return {
            "symbol": symbol,
            "available": True,
            "as_of_date": str(row.get("as_of_date")),
            "overall_score": round_score(row.get("overall_score")),
            "below_threshold": bool(row.get("below_threshold")),
            "dimensions": _mapping(row.get("dimensions")),
        }

    def get_valuation(self, symbol: str) -> dict[str, Any]:
        row = self._market.get_valuation_summary(symbol)
        if not row:
            return {"symbol": symbol, "available": False}
        return {
            "symbol": symbol,
            "available": True,
            "trade_date": str(row.get("trade_date")),
            "pe": row.get("pe"),
            "pb": row.get("pb"),
            "ev_ebitda": row.get("ev_ebitda"),
            "dividend_yield": row.get("dividend_yield"),
            "peg": row.get("peg"),
            "industry_pe_median": row.get("industry_pe_median"),
        }

    def get_peer_analysis(self, symbol: str, *, limit: int = 4) -> dict[str, Any]:
        stock = self._market.get_stock(symbol)
        if not stock:
            return {"symbol": symbol, "available": False}
        peers: list[dict[str, Any]] = []
        for peer in self._peer_symbols(symbol, limit):
            rank = _mapping(self._market.get_ranking(peer) or {})
            peers.append(
                {
                    "symbol": peer,
                    "overall_score": rank.get("overall_score"),
                    "signal": rank.get("signal"),
                }
            )
        scored = [_num(p["overall_score"]) for p in peers if p["overall_score"] is not None]
        return {
            "symbol": symbol,
            "available": True,
            "sector": str(stock.get("sector", "")),
            "peers": peers,
            "count": len(peers),
            "average_score": round(sum(scored) / len(scored), 2) if scored else None,
        }

    # ------------------------------------------------------------ news/rag
    def get_news(self, symbol: str, *, top_k: int = 5) -> dict[str, Any]:
        items = [
            n
            for n in self._market.list_news()
            if not symbol or not n.get("symbol") or n.get("symbol") == symbol
        ][:top_k]
        return {"symbol": symbol, "news": items, "count": len(items)}

    def get_corporate_events(self, symbol: str) -> dict[str, Any]:
        # No corporate-events feed wired yet (T012 news only) — structured
        # "unavailable" so Agents never fabricate events (§47).
        return {"symbol": symbol, "events": [], "available": False}

    def get_prediction(self, symbol: str) -> dict[str, Any]:
        """Generate a deterministic ML prediction using the in-process registry."""
        predictor = PredictionService(self._market)
        result = predictor.predict(symbol)
        if not result.get("available"):
            return {
                "symbol": symbol,
                "available": False,
                "reason": result.get("reason", "no trained model"),
            }
        return {
            "symbol": symbol,
            "available": True,
            "model_id": result.get("model_id", "price_direction_xgb"),
            "model_version": result.get("model_version", "1.0.0"),
            "feature_version": result.get("feature_version", "feature_v1"),
            "horizon_days": result.get("horizon_days", 5),
            "target": result.get("target", "P(return > 0) over 5TD"),
            "probability_positive": result.get("probability_positive", 0.5),
            "expected_return": result.get("expected_return", 0.0),
            "confidence": result.get("confidence", 0.0),
            "calibrated": result.get("calibrated", True),
        }

    def get_risk(self, symbol: str) -> dict[str, Any]:
        rank = _mapping(self._market.get_ranking(symbol) or {})
        rows = self._market.get_prices(symbol)
        if not rank or not rows:
            return {"symbol": symbol, "available": False}
        risk_contrib = next(
            (c for c in rank.get("contributions") or [] if _mapping(c).get("factor") == "risk"),
            None,
        )
        closes = [_num(r.get("close")) for r in rows]
        vols = [v for v in risk_engine.volatility(closes, period=20) if v is not None]
        drawdowns = [d for d in risk_engine.max_drawdown(closes) if d is not None]
        return {
            "symbol": symbol,
            "available": True,
            "risk_score": _mapping(risk_contrib).get("score") if risk_contrib else None,
            "annualized_volatility": round(vols[-1], 4) if vols else None,
            "max_drawdown": round(drawdowns[-1], 4) if drawdowns else None,
            "signal": rank.get("signal"),
            "confidence": rank.get("confidence"),
        }

    def get_ranking(self, symbol: str) -> dict[str, Any]:
        """Full scoring-engine payload: overall + signal + contributions."""
        rank = _mapping(self._market.get_ranking(symbol) or {})
        if not rank:
            return {"symbol": symbol, "available": False}
        return {"symbol": symbol, **rank, "available": True}

    def search_evidence(self, query: str, *, top_k: int = 3) -> dict[str, Any]:
        evs = self._rag.evidence_for(query, top_k=top_k)
        return {
            "query": query,
            "evidence": self._rag.evidence_payload(evs),
            "count": len(evs),
        }

    # ------------------------------------------------------------- helpers
    def _peer_symbols(self, symbol: str, limit: int) -> list[str]:
        stock = self._market.get_stock(symbol)
        if not stock:
            return []
        sector = str(stock.get("sector") or "")
        peers = [
            str(s.get("symbol"))
            for s in self._market.list_stocks(None, sector or None, None)
            if s.get("symbol") != symbol
        ]
        return peers[:limit]

    @property
    def catalog(self) -> dict[str, str]:
        """Tool name -> one-line description (registry introspection, §41)."""
        return {
            "get_stock_price": "Latest close, 20-day high/low and average volume.",
            "get_stock_profile": "Company profile (name, exchange, sector, industry).",
            "get_technical": "Technical indicators (sma20/ema12/rsi14) from the quant engine.",
            "get_fundamentals": "Data-quality/fundamental summary for a symbol.",
            "get_valuation": "Valuation summary for a symbol (P/E, P/B, DY, PEG).",
            "get_peer_analysis": "Peer stocks in the same sector with overall scores.",
            "get_market_regime": "Current market regime (BULL/BEAR/SIDEWAYS/VOLATILE).",
            "get_news": "Recent news for a symbol (market-wide items included).",
            "get_corporate_events": "Corporate events for a symbol (not wired yet).",
            "get_prediction": "ML probability/expected-return from the registry.",
            "get_risk": "Risk factor score, annualized volatility and max drawdown.",
            "get_ranking": "Full scoring-engine ranking payload for a symbol.",
            "search_evidence": "Retrieve §19 evidence objects via RAG.",
        }

    # --------------------------------------------------------------- audit
    @contextmanager
    def collect(self, sink: list[AgentToolCallRecord]) -> Iterator[list[AgentToolCallRecord]]:
        """Mirror every tool call made inside the block into ``sink`` (§13.3/§31)."""
        previous = self._recorder
        self._recorder = sink.append
        try:
            yield sink
        finally:
            self._recorder = previous

    def _record(
        self,
        name: str,
        kwargs: dict[str, Any],
        output: dict[str, Any],
        started: float,
    ) -> None:
        if self._recorder is None:
            return
        self._recorder(
            AgentToolCallRecord(
                tool_name=name,
                tool_input=dict(kwargs),
                tool_output=output,
                latency_ms=int((perf_counter() - started) * 1000),
            )
        )

    def call(self, name: str, **kwargs: Any) -> dict[str, Any]:
        """Invoke a tool by name (orchestrator + audit hook)."""
        fn = getattr(self, name, None)
        if not callable(fn) or name in ("catalog", "call", "collect"):
            raise ValueError(f"unknown tool '{name}'")
        started = perf_counter()
        try:
            result = fn(**kwargs)
        except TypeError as exc:
            self._record(name, kwargs, {"error": str(exc)}, started)
            raise ValueError(f"invalid arguments for tool '{name}': {exc}") from exc
        if not isinstance(result, dict):
            raise TypeError(f"tool '{name}' must return dict, got {type(result).__name__}")
        self._record(name, kwargs, result, started)
        return result


__all__ = ["Recorder", "ToolCatalog"]
