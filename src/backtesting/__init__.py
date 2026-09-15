"""DTCK backtesting engine (spec §16/§17, docs/BACKTESTING.md).

Public API:
    run_backtest(data, strategy, config) -> BacktestResult
"""

from src.backtesting.engine import run_backtest, select_window
from src.backtesting.metrics import compute_metrics
from src.backtesting.models import (
    BacktestConfig,
    BacktestData,
    BacktestResult,
    EquityPoint,
    ExecutionCosts,
    PriceBar,
    Trade,
)
from src.backtesting.walkforward import (
    WalkForwardWindow,
    rolling_windows,
    walk_forward_windows,
)

__all__ = [
    "run_backtest",
    "select_window",
    "compute_metrics",
    "BacktestConfig",
    "BacktestData",
    "BacktestResult",
    "EquityPoint",
    "ExecutionCosts",
    "PriceBar",
    "Trade",
    "walk_forward_windows",
    "rolling_windows",
    "WalkForwardWindow",
]
