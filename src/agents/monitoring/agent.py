"""Monitoring Agent (§20.3) — deterministic alerting on watchlist symbols.

Tracks price/volume, technical state, risk, signal changes, news and
fundamental-quality gates and emits ``AgentAlert`` objects.  Thresholds are
module constants so behaviour is auditable and unit-testable; the agent never
computes indicators itself (they come from the quant engine via tools, §47).
"""

from __future__ import annotations

from typing import Any

from src.agents.schemas import AgentAlert
from src.agents.tools import ToolCatalog
from src.agents.util import matches_important_news, round_score

PLAN: list[str] = [
    "Price & volume",
    "Technical state",
    "Risk",
    "Signal change",
    "News",
    "Fundamental quality",
]

TOOLS: tuple[str, ...] = (
    "get_stock_price",
    "get_technical",
    "get_risk",
    "get_ranking",
    "get_news",
    "get_fundamentals",
)

# ---------------------------------------------------------------- alert types
ALERT_SIGNAL_CHANGED = "signal_changed"
ALERT_RISK_INCREASED = "risk_increased"
ALERT_IMPORTANT_NEWS = "important_news"
ALERT_TECHNICAL_BREAKOUT = "technical_breakout"
ALERT_VOLUME_SPIKE = "volume_spike"
ALERT_FUNDAMENTAL_DETERIORATION = "fundamental_deterioration"

# ------------------------------------------------------------- §42 guardrails
SEVERITY_NORMAL = "normal"
SEVERITY_WARNING = "warning"
SEVERITY_CRITICAL = "critical"

RSI_OVERBOUGHT = 70.0
RSI_OVERSOLD = 30.0
RISK_SCORE_WARNING = 30.0
RISK_SCORE_CRITICAL = 20.0
QUALITY_SCORE_WARNING = 70.0
VOLUME_SPIKE_RATIO = 1.5

POLARITY_FLIPS: frozenset[tuple[str, str]] = frozenset(
    {("POSITIVE", "NEGATIVE"), ("NEGATIVE", "POSITIVE")}
)


def _alert(
    alert_type: str,
    severity: str,
    symbol: str,
    message: str,
    payload: dict[str, Any],
) -> AgentAlert:
    """Build an ``AgentAlert`` (single construction point for tests/audit)."""
    return AgentAlert(
        alert_type=alert_type,
        severity=severity,
        symbol=symbol,
        message=message,
        payload=payload,
    )


class MonitoringAgent:
    """Watches a symbol set and raises §20.3 alerts."""

    def __init__(
        self,
        tools: ToolCatalog,
        *,
        agent_id: str = "monitoring",
        version: str = "1.0",
    ) -> None:
        self._tools = tools
        self.agent_id = agent_id
        self.version = version
        self._last_signals: dict[str, str] = {}

    def reset(self) -> None:
        """Forget previously observed signals (start a new monitoring session)."""
        self._last_signals.clear()

    def monitor(
        self,
        symbols: list[str],
        *,
        previous_signals: dict[str, str] | None = None,
    ) -> list[AgentAlert]:
        """Alert for every symbol; ``previous_signals`` seeds change detection."""
        baseline = previous_signals or {}
        alerts: list[AgentAlert] = []
        for symbol in symbols:
            alerts.extend(self._symbol_alerts(symbol.upper(), baseline))
        return alerts

    def _symbol_alerts(self, symbol: str, previous_signals: dict[str, str]) -> list[AgentAlert]:
        price = self._tools.call("get_stock_price", symbol=symbol)
        if not price.get("available"):
            raise ValueError(f"symbol '{symbol}' has no price data (unknown symbol?)")
        technical = self._tools.call("get_technical", symbol=symbol)
        risk = self._tools.call("get_risk", symbol=symbol)
        ranking = self._tools.call("get_ranking", symbol=symbol)
        news = self._tools.call("get_news", symbol=symbol, top_k=5)
        fundamentals = self._tools.call("get_fundamentals", symbol=symbol)

        alerts = [
            *self._technical_alerts(symbol, price, technical),
            *self._risk_alerts(symbol, risk),
            *self._signal_alerts(symbol, ranking, previous_signals),
            *self._news_alerts(symbol, news),
            *self._quality_alerts(symbol, fundamentals),
        ]
        self._last_signals[symbol] = str(ranking.get("signal", "NEUTRAL"))
        return alerts

    # -------------------------------------------------------- alert builders
    @staticmethod
    def _technical_alerts(
        symbol: str, price: dict[str, Any], technical: dict[str, Any]
    ) -> list[AgentAlert]:
        """Breakout / RSI extreme / volume spike (§20.3 signals)."""
        out: list[AgentAlert] = []
        last, high_20, low_20 = (
            price.get("price"),
            price.get("high_20"),
            price.get("low_20"),
        )
        if last is not None and high_20 is not None and float(last) >= float(high_20):
            out.append(
                _alert(
                    ALERT_TECHNICAL_BREAKOUT,
                    SEVERITY_NORMAL,
                    symbol,
                    f"{symbol} closed at {last}, at/above the 20-day high {high_20}.",
                    {"price": last, "high_20": high_20},
                )
            )
        elif last is not None and low_20 is not None and float(last) <= float(low_20):
            out.append(
                _alert(
                    ALERT_TECHNICAL_BREAKOUT,
                    SEVERITY_WARNING,
                    symbol,
                    f"{symbol} closed at {last}, at/below the 20-day low {low_20}.",
                    {"price": last, "low_20": low_20},
                )
            )
        series = technical.get("series")
        rsi = series.get("rsi14") if isinstance(series, dict) else None
        if rsi is not None:
            if float(rsi) >= RSI_OVERBOUGHT:
                out.append(
                    _alert(
                        ALERT_TECHNICAL_BREAKOUT,
                        SEVERITY_WARNING,
                        symbol,
                        f"{symbol} RSI14 {rsi} is overbought (>= {RSI_OVERBOUGHT}).",
                        {"rsi14": rsi},
                    )
                )
            elif float(rsi) <= RSI_OVERSOLD:
                out.append(
                    _alert(
                        ALERT_TECHNICAL_BREAKOUT,
                        SEVERITY_WARNING,
                        symbol,
                        f"{symbol} RSI14 {rsi} is oversold (<= {RSI_OVERSOLD}).",
                        {"rsi14": rsi},
                    )
                )
        volume, volume_avg = price.get("volume"), price.get("volume_avg_20")
        if volume and volume_avg:
            if float(volume) >= VOLUME_SPIKE_RATIO * float(volume_avg):
                out.append(
                    _alert(
                        ALERT_VOLUME_SPIKE,
                        SEVERITY_NORMAL,
                        symbol,
                        f"{symbol} volume {volume} is >= {VOLUME_SPIKE_RATIO}x "
                        f"the 20-day average {volume_avg}.",
                        {"volume": volume, "volume_avg_20": volume_avg},
                    )
                )
        return out

    @staticmethod
    def _risk_alerts(symbol: str, risk: dict[str, Any]) -> list[AgentAlert]:
        """Risk factor score below the §42 guardrail."""
        score = risk.get("risk_score")
        if score is None:
            return []
        value = float(score)
        if value <= RISK_SCORE_CRITICAL:
            severity = SEVERITY_CRITICAL
        elif value <= RISK_SCORE_WARNING:
            severity = SEVERITY_WARNING
        else:
            return []
        return [
            _alert(
                ALERT_RISK_INCREASED,
                severity,
                symbol,
                f"{symbol} risk factor score {value:.1f} is below the "
                f"{RISK_SCORE_WARNING:.0f} guardrail.",
                {
                    "risk_score": value,
                    "max_drawdown": risk.get("max_drawdown"),
                    "annualized_volatility": risk.get("annualized_volatility"),
                },
            )
        ]

    def _signal_alerts(
        self,
        symbol: str,
        ranking: dict[str, Any],
        previous_signals: dict[str, str],
    ) -> list[AgentAlert]:
        """Signal label change since the last observation (§20.3)."""
        signal = str(ranking.get("signal", "NEUTRAL"))
        previous = previous_signals.get(symbol) or self._last_signals.get(symbol)
        if not previous or previous == signal:
            return []
        flip = (previous.upper(), signal.upper()) in POLARITY_FLIPS
        return [
            _alert(
                ALERT_SIGNAL_CHANGED,
                SEVERITY_CRITICAL if flip else SEVERITY_WARNING,
                symbol,
                f"{symbol} signal changed {previous} -> {signal}.",
                {
                    "previous_signal": previous,
                    "signal": signal,
                    "overall_score": ranking.get("overall_score"),
                },
            )
        ]

    @staticmethod
    def _news_alerts(symbol: str, news: dict[str, Any]) -> list[AgentAlert]:
        """Important-news keyword scan over the tool's news payload."""
        items = [n for n in (news.get("news") or []) if isinstance(n, dict)]
        flagged = [n for n in items if matches_important_news(str(n.get("title", "")))]
        if not flagged:
            return []
        headlines = [str(n.get("title", "")) for n in flagged]
        return [
            _alert(
                ALERT_IMPORTANT_NEWS,
                SEVERITY_WARNING,
                symbol,
                f"{symbol}: {len(flagged)} of {len(items)} news item(s) matched "
                "the risk-keyword scan.",
                {"headlines": headlines, "news_count": len(items)},
            )
        ]

    @staticmethod
    def _quality_alerts(symbol: str, fundamentals: dict[str, Any]) -> list[AgentAlert]:
        """Data-quality gate breach or low coverage score (§39)."""
        if not fundamentals.get("available"):
            return []
        score = round_score(fundamentals.get("overall_score"))
        if fundamentals.get("below_threshold"):
            return [
                _alert(
                    ALERT_FUNDAMENTAL_DETERIORATION,
                    SEVERITY_CRITICAL,
                    symbol,
                    f"{symbol} data-quality score {score:.1f} is below the §39 gate.",
                    {"overall_score": score, "below_threshold": True},
                )
            ]
        if score < QUALITY_SCORE_WARNING:
            return [
                _alert(
                    ALERT_FUNDAMENTAL_DETERIORATION,
                    SEVERITY_WARNING,
                    symbol,
                    f"{symbol} data-quality score {score:.1f} is below "
                    f"{QUALITY_SCORE_WARNING:.0f}.",
                    {"overall_score": score, "below_threshold": False},
                )
            ]
        return []


__all__ = [
    "ALERT_FUNDAMENTAL_DETERIORATION",
    "ALERT_IMPORTANT_NEWS",
    "ALERT_RISK_INCREASED",
    "ALERT_SIGNAL_CHANGED",
    "ALERT_TECHNICAL_BREAKOUT",
    "ALERT_VOLUME_SPIKE",
    "PLAN",
    "SEVERITY_CRITICAL",
    "SEVERITY_NORMAL",
    "SEVERITY_WARNING",
    "TOOLS",
    "MonitoringAgent",
]
