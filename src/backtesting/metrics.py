"""Backtest performance metrics (SYSTEM_SPECIFICATION §16, BACKTESTING.md §3).

Pure functions over an equity curve (EquityPoint) and realized trades. Trading
days per year is configurable (default 252). Deterministic; degenerate inputs
return 0.0 rather than raising.
"""

from __future__ import annotations

from math import sqrt

from src.backtesting.models import EquityPoint, Trade

__all__ = [
    "total_return", "cagr", "annualized_volatility", "sharpe_ratio", "sortino_ratio",
    "max_drawdown", "calmar_ratio", "win_rate", "profit_factor", "turnover",
    "transaction_cost_total", "compute_metrics",
]

TRADING_DAYS = 252


def _equity_values(curve: list[EquityPoint]) -> list[float]:
    return [p.equity for p in curve]


def _per_period_returns(curve: list[EquityPoint], risk_free_rate: float = 0.0) -> list[float]:
    rf_period = (1.0 + risk_free_rate) ** (1.0 / TRADING_DAYS) - 1.0
    vals = _equity_values(curve)
    out: list[float] = []
    for i in range(1, len(vals)):
        if vals[i - 1] != 0:
            out.append(vals[i] / vals[i - 1] - 1.0 - rf_period)
    return out


def total_return(curve: list[EquityPoint]) -> float:
    if len(curve) < 2 or curve[0].equity == 0:
        return 0.0
    return float(curve[-1].equity / curve[0].equity) - 1.0


def cagr(curve: list[EquityPoint], trading_days: int = TRADING_DAYS) -> float:
    if len(curve) < 2 or curve[0].equity <= 0:
        return 0.0
    years = (len(curve) - 1) / trading_days
    if years <= 0:
        return 0.0
    growth = curve[-1].equity / curve[0].equity
    return float(growth ** (1.0 / years)) - 1.0


def annualized_volatility(curve: list[EquityPoint], trading_days: int = TRADING_DAYS) -> float:
    returns = _per_period_returns(curve)
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / len(returns)
    return sqrt(var) * sqrt(trading_days)


def sharpe_ratio(curve: list[EquityPoint], risk_free_rate: float = 0.0) -> float:
    returns = _per_period_returns(curve, risk_free_rate)
    if not returns:
        return 0.0
    excess_mean = sum(returns) / len(returns)
    var = sum((r - excess_mean) ** 2 for r in returns) / len(returns)
    if var == 0:
        return 0.0
    return (excess_mean / sqrt(var)) * sqrt(TRADING_DAYS)


def sortino_ratio(curve: list[EquityPoint], risk_free_rate: float = 0.0) -> float:
    returns = _per_period_returns(curve, risk_free_rate)
    if not returns:
        return 0.0
    excess_mean = sum(returns) / len(returns)
    downside = [r for r in returns if r < 0]
    if not downside:
        return 0.0
    downside_dev = sqrt(sum(r * r for r in downside) / len(downside))
    if downside_dev == 0:
        return 0.0
    return (excess_mean / downside_dev) * sqrt(TRADING_DAYS)


def max_drawdown(curve: list[EquityPoint]) -> float:
    """Negative fraction of the worst peak-to-trough decline."""
    peak = float("-inf")
    worst = 0.0
    for v in _equity_values(curve):
        if v > peak:
            peak = v
        if peak > 0:
            dd = v / peak - 1.0
            if dd < worst:
                worst = dd
    return worst


def calmar_ratio(curve: list[EquityPoint], trading_days: int = TRADING_DAYS) -> float:
    dd = max_drawdown(curve)
    if dd == 0:
        return 0.0
    return cagr(curve, trading_days) / abs(dd)


def win_rate(trades: list[Trade]) -> float:
    closed = [t for t in trades if t.pnl is not None]
    if not closed:
        return 0.0
    return float(sum(1 for t in closed if (t.pnl or 0) > 0) / len(closed))


def profit_factor(trades: list[Trade]) -> float:
    gross_profit = sum(t.pnl for t in trades if t.pnl is not None and t.pnl > 0)
    gross_loss = sum(abs(t.pnl) for t in trades if t.pnl is not None and t.pnl < 0)
    if gross_loss == 0:
        return 0.0 if gross_profit == 0 else float("inf")
    return gross_profit / gross_loss


def turnover(trades: list[Trade], initial_capital: float) -> float:
    """Traded notional (entry + exit legs) / initial capital."""
    traded = sum(
        t.entry_price * t.quantity + (t.exit_price or 0.0) * t.quantity for t in trades
    )
    if initial_capital <= 0:
        return 0.0
    return traded / initial_capital


def transaction_cost_total(
    trades: list[Trade], commission_bps: float, slippage_bps: float
) -> float:
    """Both entry and exit fills incur costs (mirrors the engine's cash flow)."""
    bps = (commission_bps + slippage_bps) / 10_000.0
    total = 0.0
    for t in trades:
        total += t.entry_price * t.quantity * bps
        if t.exit_price is not None:
            total += t.exit_price * t.quantity * bps
    return total


def compute_metrics(
    curve: list[EquityPoint],
    trades: list[Trade],
    *,
    initial_capital: float,
    commission_bps: float = 15.0,
    slippage_bps: float = 5.0,
    trading_days: int = TRADING_DAYS,
    traded_notional: float | None = None,
    execution_cost: float | None = None,
) -> dict[str, float]:
    """Performance metrics for one run.

    ``traded_notional`` / ``execution_cost`` are the engine's *actual* fills
    (source of truth). When omitted, they are estimated from the trade log so
    direct callers of this pure function still get sensible numbers.
    """
    return {
        "total_return": total_return(curve),
        "cagr": cagr(curve, trading_days),
        "annualized_volatility": annualized_volatility(curve, trading_days),
        "sharpe_ratio": sharpe_ratio(curve),
        "sortino_ratio": sortino_ratio(curve),
        "max_drawdown": max_drawdown(curve),
        "calmar_ratio": calmar_ratio(curve, trading_days),
        "win_rate": win_rate(trades),
        "profit_factor": profit_factor(trades),
        "turnover": (
            turnover(trades, initial_capital)
            if traded_notional is None
            else (traded_notional / initial_capital if initial_capital > 0 else 0.0)
        ),
        "transaction_cost": (
            transaction_cost_total(trades, commission_bps, slippage_bps)
            if execution_cost is None
            else execution_cost
        ),
    }
