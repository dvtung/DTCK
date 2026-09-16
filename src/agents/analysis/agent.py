"""Analysis Agent (§20.2) — deterministic quant+RAG synthesis.

Calls Quant Tools + RAG Tools for one symbol, then builds the §23
``InvestmentAnalysis``: factor scores from the scoring engine, a template
thesis from signal + top/bottom contributions, catalysts/risks derived from
factor extremes, invalidation conditions from regime/risk, confidence from the
§24 blend, and the §19 evidence list from RAG.
"""

from __future__ import annotations

from typing import Any

from src.agents.schemas import InvestmentAnalysis
from src.agents.tools import ToolCatalog
from src.agents.util import bottom_factor, clamp01, round_score, signal_word, top_factor

PLAN: list[str] = [
    "Market regime",
    "Price",
    "Technical",
    "Fundamental",
    "Valuation",
    "Peer comparison",
    "News",
    "Corporate events",
    "Risk",
    "ML prediction",
    "Investment thesis",
]

TOOLS: tuple[str, ...] = (
    "get_market_regime",
    "get_stock_price",
    "get_technical",
    "get_fundamentals",
    "get_valuation",
    "get_peer_analysis",
    "get_news",
    "get_corporate_events",
    "get_prediction",
    "get_risk",
    "get_ranking",
    "search_evidence",
)

# §24 confidence weights — MVP baseline blend.  The spec leaves the official
# formula open until a historical dataset exists; these weights are explicit so
# the number is reproducible and auditable (see KI-012).
CONFIDENCE_WEIGHTS: dict[str, float] = {
    "model_reliability": 0.30,
    "data_quality": 0.30,
    "regime_compatibility": 0.20,
    "evidence_quality": 0.10,
    "signal_agreement": 0.10,
}

# Factor → catalyst phrasing (unused factors simply yield no catalyst line).
CATALYST_FACTORS: dict[str, str] = {
    "fundamental": "Fundamental score above the model baseline",
    "momentum": "Positive price/volume momentum",
    "valuation": "Valuation factor supportive",
    "technical": "Technical setup supportive",
    "quality": "Data-quality coverage complete",
    "risk": "Risk profile contained",
}


def _pct(value: object) -> str:
    """Format a 0-1 share as a percentage string (deterministic)."""
    return f"{round_score(value, 4):.2%}"


def _series(payload: dict[str, Any]) -> dict[str, Any]:
    """Narrow a tool payload's ``series`` mapping."""
    value = payload.get("series")
    return value if isinstance(value, dict) else {}


class AnalysisAgent:
    """Produces an ``InvestmentAnalysis`` for one symbol (§20.2/§23)."""

    def __init__(
        self,
        tools: ToolCatalog,
        *,
        agent_id: str = "analysis",
        version: str = "1.0",
    ) -> None:
        self._tools = tools
        self.agent_id = agent_id
        self.version = version

    def analyze(self, symbol: str) -> InvestmentAnalysis:
        regime = self._tools.call("get_market_regime")
        price = self._tools.call("get_stock_price", symbol=symbol)
        tech = self._tools.call("get_technical", symbol=symbol)
        fund = self._tools.call("get_fundamentals", symbol=symbol)
        val = self._tools.call("get_valuation", symbol=symbol)
        peers = self._tools.call("get_peer_analysis", symbol=symbol)
        news = self._tools.call("get_news", symbol=symbol)
        risk = self._tools.call("get_risk", symbol=symbol)
        events = self._tools.call("get_corporate_events", symbol=symbol)
        prediction = self._tools.call("get_prediction", symbol=symbol)
        evidence = self._tools.call(
            "search_evidence", query=f"{symbol} investment analysis", top_k=4
        )

        rank = self._tools.call("get_ranking", symbol=symbol)
        if not rank.get("available"):
            raise ValueError(f"symbol '{symbol}' has no ranking (unknown symbol?)")

        scores = {c["factor"]: c["score"] for c in rank["contributions"]}
        contributions = {c["factor"]: c["contribution_pct"] for c in rank["contributions"]}

        overall = round_score(rank.get("overall_score"), 2)
        signal = str(rank.get("signal", "NEUTRAL"))
        top, _ = top_factor(contributions)
        ordered = sorted(contributions, key=lambda k: float(contributions[k] or 0.0), reverse=True)
        second = ordered[1] if len(ordered) > 1 else top

        thesis = self._build_thesis(symbol, signal, overall, top, second, regime, price, peers)
        catalysts = self._catalysts(contributions, news, events)
        risks = self._risks(contributions, risk, regime, val)
        invalidation = self._invalidations(regime, risk, top)
        warnings = self._warnings(tech, prediction, events)

        confidence = self._confidence(
            signal=signal,
            data_quality=fund.get("overall_score"),
            evidence_count=int(evidence.get("count", 0)),
            regime_compat=float(regime.get("confidence", 0.5)),
            ranking_conf=float(rank["confidence"]),
        )

        return InvestmentAnalysis(
            symbol=symbol,
            overall_score=round_score(overall),
            market_regime=str(regime.get("regime", "UNKNOWN")),
            technical_score=round_score(scores.get("technical")),
            fundamental_score=round_score(scores.get("fundamental")),
            valuation_score=round_score(scores.get("valuation")),
            momentum_score=round_score(scores.get("momentum")),
            risk_score=round_score(scores.get("risk")),
            thesis=thesis,
            catalysts=catalysts,
            risks=risks,
            invalidation_conditions=invalidation,
            confidence=round_score(confidence, 4),
            evidence=list(evidence.get("evidence", [])),
            warnings=warnings,
        )

    # ------------------------------------------------------------ thesis
    @staticmethod
    def _peer_avg(peers: dict[str, Any]) -> float | None:
        """Average peer score reported by the ``get_peer_analysis`` tool."""
        value = peers.get("average_score")
        return round_score(value, 2) if value is not None else None

    def _build_thesis(
        self,
        symbol: str,
        signal: str,
        overall: float,
        top: str,
        second: str,
        regime: dict[str, Any],
        price: dict[str, Any],
        peers: dict[str, Any],
    ) -> str:
        """Template thesis from signal + dominant factors (§25 item 1)."""
        peer_avg = self._peer_avg(peers)
        peer_txt = f"{peer_avg:.1f}" if peer_avg is not None else "n/a"
        parts = [
            f"{symbol} scores {overall:.1f}/100 on the multi-factor model "
            f"({signal_word(signal)}), led by {top or 'n/a'} and {second or 'n/a'}."
        ]
        if price.get("available"):
            parts.append(
                f"Last close {price.get('price')} "
                f"({round_score(price.get('change_pct'), 4):+.2%}) on "
                f"{price.get('trade_date')}, 20-day range "
                f"{price.get('low_20')}-{price.get('high_20')}."
            )
        parts.append(
            f"Market regime {regime.get('regime', 'UNKNOWN')} "
            f"(confidence {round_score(regime.get('confidence'), 4):.2f}); "
            f"sector peers average {peer_txt} (n={peers.get('count', 0)})."
        )
        return " ".join(parts)

    def _catalysts(
        self,
        contributions: dict[str, float | None],
        news: dict[str, Any],
        events: dict[str, Any],
    ) -> list[str]:
        """Catalysts = strongest factors + important news + events (§25 §7)."""
        out: list[str] = []
        ranked = sorted(contributions, key=lambda k: float(contributions[k] or 0.0), reverse=True)
        for factor in ranked:
            if len(out) >= 2:
                break
            text = CATALYST_FACTORS.get(factor)
            if text and contributions.get(factor) is not None:
                out.append(f"{text} ({factor} contribution {_pct(contributions[factor])}).")
        for item in (news.get("news") or [])[:2]:
            if isinstance(item, dict):
                title = str(item.get("title", "")).strip()
                source = str(item.get("source", "")).strip()
                if title:
                    out.append(f"News flow: {title} ({source or 'unknown source'}).")
        for event in events.get("events") or []:
            if isinstance(event, dict):
                label = event.get("title", event.get("type", ""))
                out.append(f"Corporate event: {label}.")
        if not out:
            out.append("No catalyst identified from the available data.")
        return out

    def _risks(
        self,
        contributions: dict[str, float | None],
        risk: dict[str, Any],
        regime: dict[str, Any],
        valuation: dict[str, Any],
    ) -> list[str]:
        """Risks from the weakest factor, risk metrics, regime, valuation (§25 §8)."""
        out: list[str] = []
        weakest, share = bottom_factor(contributions)
        if weakest:
            out.append(f"Weakest factor is {weakest} (contribution {_pct(share)}).")
        drawdown = risk.get("max_drawdown")
        if drawdown is not None:
            out.append(f"Realised max drawdown {round_score(drawdown, 4):.2%}.")
        volatility = risk.get("annualized_volatility")
        if volatility is not None:
            out.append(f"Annualized volatility {round_score(volatility, 4):.2%}.")
        regime_name = str(regime.get("regime", "UNKNOWN"))
        if regime_name in ("BEAR", "VOLATILE"):
            out.append(f"Market regime {regime_name} raises beta/regime risk.")
        pe, median = valuation.get("pe"), valuation.get("industry_pe_median")
        if pe is not None and median is not None and float(pe) > float(median):
            out.append(f"P/E {pe} above the industry median {median} (valuation risk).")
        if not out:
            out.append("No elevated risk detected in the available data.")
        return out

    @staticmethod
    def _invalidations(regime: dict[str, Any], risk: dict[str, Any], top: str) -> list[str]:
        """Falsifiable conditions that would invalidate the thesis (§25 §10)."""
        out = ["Overall score falls below 40 (signal flips to NEGATIVE)."]
        if top:
            out.append(f"The {top} factor loses its lead in the contribution mix.")
        out.append(f"Market regime flips to BEAR (currently {regime.get('regime', 'UNKNOWN')}).")
        drawdown = risk.get("max_drawdown")
        if drawdown is not None:
            out.append(f"Drawdown deepens beyond {abs(round_score(drawdown, 4)):.2%}.")
        else:
            out.append("Drawdown exceeds the 20% guardrail (§42).")
        return out

    @staticmethod
    def _warnings(
        technical: dict[str, Any],
        prediction: dict[str, Any],
        events: dict[str, Any],
    ) -> list[str]:
        """Honest gaps in the analysis inputs (§3/§47)."""
        out: list[str] = []
        if not technical.get("available"):
            out.append("Technical indicators unavailable for this symbol.")
        else:
            missing = sorted(name for name, value in _series(technical).items() if value is None)
            if missing:
                out.append("Indicator warmup incomplete: " + ", ".join(missing) + ".")
        if not prediction.get("available"):
            out.append("ML prediction unavailable (T014 pending) — quant + RAG only.")
        if not events.get("available"):
            out.append(
                "Corporate-events feed not wired (T012 news only) — event risk not assessed."
            )
        return out

    @staticmethod
    def _confidence(
        *,
        signal: str,
        data_quality: object,
        evidence_count: int,
        regime_compat: float,
        ranking_conf: float,
    ) -> float:
        """§24 confidence blend: reliability × data quality × regime × evidence.

        The spec keeps the official formula open until a historical dataset
        exists, so this is an explicit, documented MVP baseline (see
        ``CONFIDENCE_WEIGHTS`` / KI-012) — never a hidden constant.
        """
        model_reliability = clamp01(0.5 + 0.5 * ranking_conf)
        quality = clamp01(round_score(data_quality, 4) / 100.0)
        regime = clamp01(regime_compat)
        evidence = clamp01(min(evidence_count, 4) / 4.0)
        agreement = {"POSITIVE": 1.0, "NEGATIVE": 0.9, "NEUTRAL": 0.7}.get(signal.upper(), 0.7)
        confidence = (
            CONFIDENCE_WEIGHTS["model_reliability"] * model_reliability
            + CONFIDENCE_WEIGHTS["data_quality"] * quality
            + CONFIDENCE_WEIGHTS["regime_compatibility"] * regime
            + CONFIDENCE_WEIGHTS["evidence_quality"] * evidence
            + CONFIDENCE_WEIGHTS["signal_agreement"] * agreement
        )
        return clamp01(round(confidence, 4))


__all__ = ["CATALYST_FACTORS", "CONFIDENCE_WEIGHTS", "PLAN", "TOOLS", "AnalysisAgent"]
