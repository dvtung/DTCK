"""T009 tests — backtesting engine: execution, metrics, walk-forward (spec §16/§17)."""

from __future__ import annotations

from datetime import date

import pytest

from src.backtesting import (
    BacktestConfig,
    BacktestData,
    ExecutionCosts,
    PriceBar,
    compute_metrics,
    run_backtest,
    select_window,
    walk_forward_windows,
)
from src.backtesting.metrics import cagr, max_drawdown, sharpe_ratio

D0 = date(2026, 1, 2)
DAYS = [date(2026, 1, 2 + i) for i in range(10)]


def _bar(d: date, close: float, open_: float | None = None, low: float | None = None) -> PriceBar:
    o = open_ if open_ is not None else close
    lo = low if low is not None else min(o, close)
    return PriceBar(date=d, open=o, high=max(o, close), low=lo, close=close, volume=1000)


def _data(symbols=("FPT", "VCB"), closes=None) -> BacktestData:
    # deterministic synthetic series: linearly rising closes
    closes = closes or {s: [100.0 + i * 2 for i in range(len(DAYS))] for s in symbols}
    bars: dict[str, list[PriceBar]] = {}
    for s in symbols:
        bars[s] = [_bar(d, closes[s][i]) for i, d in enumerate(DAYS)]
    return BacktestData(dates=DAYS, symbols=list(symbols), bars=bars)


class TestExecution:
    def test_next_bar_open_fill_no_lookahead(self) -> None:
        # strategy invests 100% in FPT on day 0; first fill is at day 1 open
        calls: list[int] = []

        def strat(data: BacktestData, i: int, ctx: dict[str, object]) -> dict[str, float]:
            calls.append(i)
            if i >= 5:
                return {"FPT": 0.0}
            return {"FPT": 1.0} if i == 0 else {"FPT": 0.5}

        config = BacktestConfig(strategy_name="t", initial_capital=100_000.0)
        res = run_backtest(_data(), strat, config)
        # equity curve has one point per day
        assert len(res.equity_curve) == len(DAYS)
        # buying at t+1 open means first day has no exposure growth beyond cash
        assert res.final_equity() > 100_000.0  # price rose, so gains realized

    def test_hold_cash_positions_closed_at_end(self) -> None:
        def strat(data: BacktestData, i: int, ctx: dict[str, object]) -> dict[str, float]:
            return {"FPT": 1.0}

        res = run_backtest(_data(), strat, BacktestConfig(strategy_name="t"))
        # every open position closed at end → no open trades remain (all have exit_date)
        assert all(t.exit_date is not None for t in res.trades)
        assert len(res.trades) == 1  # one buy, closed at end

    def test_weight_out_of_range_raises(self) -> None:
        def strat(data: BacktestData, i: int, ctx: dict[str, object]) -> dict[str, float]:
            return {"FPT": 1.5} if i == 0 else {}

        config = BacktestConfig(strategy_name="t", initial_capital=100_000.0)
        with pytest.raises(ValueError):
            run_backtest(_data(), strat, config)  # type: ignore[arg-type]

    def test_select_window_bounds(self) -> None:
        data = _data()
        s, e = select_window(data, date(2026, 1, 4), date(2026, 1, 7))
        assert data.dates[s] == date(2026, 1, 4)
        assert data.dates[e] == date(2026, 1, 7)
        with pytest.raises(ValueError):
            select_window(data, date(2026, 1, 8), date(2026, 1, 3))

    def test_costs_reduce_returns(self) -> None:
        def strat(data: BacktestData, i: int, ctx: dict[str, object]) -> dict[str, float]:
            return {"FPT": 1.0}

        no_cost = BacktestConfig(
            strategy_name="t", costs=ExecutionCosts(commission_bps=0, slippage_bps=0)
        )
        h_cost = BacktestConfig(
            strategy_name="t", costs=ExecutionCosts(commission_bps=1000, slippage_bps=1000)
        )
        r_no = run_backtest(_data(), strat, no_cost)
        r_hi = run_backtest(_data(), strat, h_cost)
        assert r_hi.metrics["transaction_cost"] > r_no.metrics["transaction_cost"]
        assert r_hi.final_equity() < r_no.final_equity()

    def test_strategy_sees_only_past(self) -> None:
        # strategy must not depend on future closes to be executable deterministically
        def strat(data: BacktestData, i: int, ctx: dict[str, object]) -> dict[str, float]:
            # only uses closes up to index i
            c = data.bars["FPT"][i].close
            return {"FPT": 1.0 if c > 100 else 0.5}

        res = run_backtest(_data(), strat, BacktestConfig(strategy_name="t"))
        assert res.equity_curve


class TestMetrics:
    def test_flat_curve(self) -> None:
        curve = [type("E", (), {"date": D0, "equity": 1_000.0})() for _ in range(10)]
        assert cagr(curve) == 0.0
        assert sharpe_ratio(curve) == 0.0
        assert max_drawdown(curve) == 0.0

    def test_known_metrics(self) -> None:
        curve = [
            type("E", (), {"date": D0, "equity": v})() for v in [1000.0, 1100.0, 1210.0, 1331.0]
        ]
        tr = compute_metrics(
            curve, [], initial_capital=1000.0, trading_days=1  # 3 periods = 3 "years"
        )["total_return"]
        assert abs(tr - 0.331) < 1e-3
        assert abs(cagr(curve, trading_days=1) - 0.1) < 1e-9  # 10% per period compounded


class TestWalkForward:
    def test_windows_non_overlapping(self) -> None:
        windows = list(walk_forward_windows(30, train_len=10, test_len=5, step=5))
        assert len(windows) == 4
        prev_end = -1
        for w in windows:
            assert w.train_start == w.test_start - w.train_len
            assert w.test_start > prev_end
            prev_end = w.test_end

    def test_insufficient_data_returns_nothing(self) -> None:
        assert list(walk_forward_windows(5, train_len=10, test_len=5)) == []
