"""Portfolio Agent (§20.4/§27) — concentration, exposure, drawdown, risk budget.

Portfolio conclusions are deliberately separate from stock ranking (§27): the
input is a position list, the output is a ``PortfolioRiskSnapshot``.  Every
price/score/volatility number comes from a tool call (§22/§47); the agent only
aggregates them into portfolio-level exposure.
"""

from __future__ import annotations

from typing import Any

from src.agents.schemas import AgentAlert, PortfolioPosition, PortfolioRiskSnapshot
from src.agents.tools import ToolCatalog
from src.agents.util import round_score

PLAN: list[str] = [
    "Positions & market value",
    "Factor scores",
    "Concentration",
    "Sector exposure",
    "Drawdown",
    "Risk budget",
]

TOOLS: tuple[str, ...] = (
    "get_stock_price",
    "get_stock_profile",
    "get_ranking",
    "get_risk",
)

# §42 guardrail defaults (overridable per call for scenario analysis).
RISK_BUDGET_ANNUAL_VOL = 0.20
MAX_POSITION_PCT = 30.0
MAX_POSITION_PCT_CRITICAL = 50.0
MAX_SECTOR_PCT = 40.0
MAX_NEGATIVE_SIGNAL_PCT = 20.0


class PortfolioAgent:
    """Computes a portfolio-level risk snapshot (§20.4/§27)."""

    def __init__(
        self,
        tools: ToolCatalog,
        *,
        agent_id: str = "portfolio",
        version: str = "1.0",
    ) -> None:
        self._tools = tools
        self.agent_id = agent_id
        self.version = version

    def analyze(
        self,
        positions: list[PortfolioPosition],
        *,
        risk_budget_annual_vol: float = RISK_BUDGET_ANNUAL_VOL,
    ) -> PortfolioRiskSnapshot:
        """Aggregate positions into a portfolio risk snapshot.

        Raises ``ValueError`` for an empty portfolio or an unknown symbol.
        """
        rows = [self._position_row(p) for p in positions]
        total_value = sum(r["value"] for r in rows)
        if total_value <= 0:
            raise ValueError("portfolio has no market value to analyse")
        for row in rows:
            row["weight"] = row["value"] / total_value

        top_concentration = max(r["weight"] for r in rows) * 100.0
        sector_weights = self._sector_weights(rows)
        max_sector = max(sector_weights.values()) * 100.0 if sector_weights else 0.0
        avg_score = self._weighted(rows, "score")
        portfolio_vol = sum(
            round_score(r["weight"], 6) * round_score(r["volatility"], 6)
            for r in rows
            if r["volatility"] is not None
        )
        max_drawdown_est = sum(
            round_score(r["weight"], 6) * round_score(r["max_drawdown"], 6)
            for r in rows
            if r["max_drawdown"] is not None
        )
        budget_used = (
            100.0 * portfolio_vol / risk_budget_annual_vol if risk_budget_annual_vol > 0 else 0.0
        )

        return PortfolioRiskSnapshot(
            total_value=round(total_value, 2),
            positions=len(rows),
            top_concentration_pct=round(top_concentration, 2),
            max_sector_pct=round(max_sector, 2),
            avg_score=round(avg_score, 2),
            max_drawdown_est=round(max_drawdown_est, 4),
            risk_budget_used_pct=round(budget_used, 2),
            warnings=self._warnings(rows),
            alerts=self._alerts(rows, top_concentration, sector_weights, budget_used),
        )

    @staticmethod
    def _weighted(rows: list[dict[str, Any]], key: str) -> float:
        """Weight-weighted average of a row value (0 when nothing is scored)."""
        scored = [r for r in rows if r[key] is not None]
        denominator = sum(round_score(r["weight"], 6) for r in scored)
        if not scored or denominator <= 0:
            return 0.0
        numerator = sum(round_score(r["weight"], 6) * round_score(r[key], 6) for r in scored)
        return numerator / denominator

    @staticmethod
    def _sector_weights(rows: list[dict[str, Any]]) -> dict[str, float]:
        """Sector → portfolio weight mapping (§27 sector exposure)."""
        weights: dict[str, float] = {}
        for row in rows:
            sector = str(row["sector"]) or "UNKNOWN"
            weights[sector] = weights.get(sector, 0.0) + round_score(row["weight"], 6)
        return weights

    def _position_row(self, position: PortfolioPosition) -> dict[str, Any]:
        """One position enriched with tool-sourced price/sector/score/risk."""
        symbol = position.symbol.upper()
        price = self._tools.call("get_stock_price", symbol=symbol)
        if not price.get("available"):
            raise ValueError(f"symbol '{symbol}' has no price data (unknown symbol?)")
        profile = self._tools.call("get_stock_profile", symbol=symbol)
        ranking = self._tools.call("get_ranking", symbol=symbol)
        risk = self._tools.call("get_risk", symbol=symbol)
        return {
            "symbol": symbol,
            "quantity": float(position.quantity),
            "price": price.get("price"),
            "value": float(position.quantity) * round_score(price.get("price"), 4),
            "sector": str(profile.get("sector", "")) or "UNKNOWN",
            "score": ranking.get("overall_score"),
            "signal": str(ranking.get("signal", "NEUTRAL")),
            "volatility": risk.get("annualized_volatility"),
            "max_drawdown": risk.get("max_drawdown"),
            "weight": 0.0,
        }

    @staticmethod
    def _warnings(rows: list[dict[str, Any]]) -> list[str]:
        """Honest limits of the snapshot (§3/§47)."""
        out: list[str] = []
        if len(rows) == 1:
            out.append("Single-position portfolio — diversification metrics degenerate.")
        if len(rows) > 1:
            out.append(
                "Correlation is not modelled yet (§27) — risk budget is an "
                "undiversified upper bound."
            )
        if any(r["volatility"] is None for r in rows):
            out.append("Volatility unavailable for at least one position.")
        if any(r["score"] is None for r in rows):
            out.append("Factor score unavailable for at least one position.")
        return out

    @staticmethod
    def _alerts(
        rows: list[dict[str, Any]],
        top_concentration: float,
        sector_weights: dict[str, float],
        budget_used: float,
    ) -> list[AgentAlert]:
        """§42 guardrail breaches (concentration, sector, signal, risk budget)."""
        out: list[AgentAlert] = []
        worst = max(rows, key=lambda r: round_score(r["weight"], 6))
        if top_concentration > MAX_POSITION_PCT:
            severity = "critical" if top_concentration > MAX_POSITION_PCT_CRITICAL else "warning"
            out.append(
                AgentAlert(
                    alert_type="concentration",
                    severity=severity,
                    symbol=str(worst["symbol"]),
                    message=(
                        f"{worst['symbol']} is {top_concentration:.1f}% of the "
                        f"portfolio (limit {MAX_POSITION_PCT:.0f}%)."
                    ),
                    payload={"top_concentration_pct": round(top_concentration, 2)},
                )
            )
        if sector_weights:
            sector, weight = max(sector_weights.items(), key=lambda kv: kv[1])
            if weight * 100.0 > MAX_SECTOR_PCT:
                out.append(
                    AgentAlert(
                        alert_type="sector_exposure",
                        severity="warning",
                        symbol=str(worst["symbol"]),
                        message=(
                            f"Sector {sector} is {weight * 100.0:.1f}% of the "
                            f"portfolio (limit {MAX_SECTOR_PCT:.0f}%)."
                        ),
                        payload={"sector": sector, "weight": round(weight, 6)},
                    )
                )
        negative = sum(
            round_score(r["weight"], 6) for r in rows if str(r["signal"]).upper() == "NEGATIVE"
        )
        if negative * 100.0 >= MAX_NEGATIVE_SIGNAL_PCT:
            out.append(
                AgentAlert(
                    alert_type="signal_exposure",
                    severity="warning",
                    symbol=str(worst["symbol"]),
                    message=(
                        f"{negative * 100.0:.1f}% of the portfolio is in NEGATIVE-signal positions."
                    ),
                    payload={"negative_weight": round(negative, 6)},
                )
            )
        if budget_used > 100.0:
            out.append(
                AgentAlert(
                    alert_type="risk_budget",
                    severity="critical",
                    symbol=str(worst["symbol"]),
                    message=(
                        f"Risk budget used {budget_used:.1f}% > 100% (§42 volatility guardrail)."
                    ),
                    payload={"risk_budget_used_pct": round(budget_used, 2)},
                )
            )
        return out


__all__ = [
    "MAX_POSITION_PCT",
    "MAX_SECTOR_PCT",
    "PLAN",
    "RISK_BUDGET_ANNUAL_VOL",
    "TOOLS",
    "PortfolioAgent",
]
