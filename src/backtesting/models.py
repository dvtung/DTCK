"""Backtesting data models (doc BACKTESTING.md §2, §6, §7).

Pure dataclasses — no database or external dependencies. Aligned price series
drive a next-bar-open execution simulation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

__all__ = [
    "PriceBar",
    "BacktestData",
    "ExecutionCosts",
    "Trade",
    "EquityPoint",
    "BacktestConfig",
    "BacktestResult",
]


@dataclass(frozen=True)
class PriceBar:
    """One row of aligned market data for a single date."""

    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class BacktestData:
    """Aligned multi-symbol price data.

    ``dates`` is the master calendar. Each symbol's arrays in ``bars`` must be
    the same length as ``dates`` (index-aligned). ``benchmark`` is an optional
    index series (e.g. VNINDEX) used for alpha-tracking metrics.
    """

    dates: list[date]
    symbols: list[str]
    bars: dict[str, list[PriceBar]]
    benchmark: list[PriceBar] = field(default_factory=list)

    def close_at(self, symbol: str, i: int) -> float:
        return self.bars[symbol][i].close

    def open_at(self, symbol: str, i: int) -> float:
        return self.bars[symbol][i].open


@dataclass(frozen=True)
class ExecutionCosts:
    """Transaction costs recorded per trade (BACKTESTING.md §6)."""

    commission_bps: float = 15.0  # broker commission (basis points)
    slippage_bps: float = 5.0  # execution slippage (basis points)


@dataclass
class Trade:
    """A completed (or open) position leg."""

    symbol: str
    entry_date: date
    exit_date: date | None
    entry_price: float
    exit_price: float | None
    quantity: float
    pnl: float | None
    return_pct: float | None


@dataclass
class EquityPoint:
    """Equity curve point (mark-to-market at close)."""

    date: date
    equity: float


@dataclass(frozen=True)
class BacktestConfig:
    """Backtest run configuration (mirrors ``backtests`` table fields)."""

    strategy_name: str
    strategy_version: str = "0.1.0"
    universe: list[str] = field(default_factory=list)
    start_date: date | None = None
    end_date: date | None = None
    params: dict[str, object] = field(default_factory=dict)
    initial_capital: float = 1_000_000.0
    costs: ExecutionCosts = field(default_factory=ExecutionCosts)
    run_type: str = "walk-forward"


@dataclass
class BacktestResult:
    """Result of a backtest run."""

    config: BacktestConfig
    equity_curve: list[EquityPoint]
    trades: list[Trade]
    metrics: dict[str, float]

    def final_equity(self) -> float:
        return self.equity_curve[-1].equity if self.equity_curve else self.config.initial_capital
