"""Unit tests for the GĐ 5 strategy backtest (pure pieces)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.backtesting.models import BacktestData, PriceBar
from src.quant.strategy.backtest import (
    build_strategy,
    rebalance_dates,
    top_weights,
)


def _dates(n: int) -> list[date]:
    start = date(2026, 1, 1)
    return [start + timedelta(days=i) for i in range(n)]


class TestRebalanceDates:
    def test_first_date_then_every_n(self) -> None:
        dates = _dates(10)
        assert rebalance_dates(dates, every_days=3) == [
            dates[0],
            dates[3],
            dates[6],
            dates[9],
        ]

    def test_every_day_is_every_date(self) -> None:
        dates = _dates(4)
        assert rebalance_dates(dates, every_days=1) == dates

    def test_empty_and_invalid(self) -> None:
        assert rebalance_dates([], every_days=21) == []
        with pytest.raises(ValueError, match="every_days"):
            rebalance_dates(_dates(5), every_days=0)


class TestTopWeights:
    def test_top_n_equal_weights(self) -> None:
        weights = top_weights({"AAA": 90.0, "BBB": 80.0, "CCC": 70.0}, 2)
        assert weights == {"AAA": 0.5, "BBB": 0.5}
        assert sum(weights.values()) == pytest.approx(1.0)

    def test_ties_broken_by_symbol_for_determinism(self) -> None:
        weights = top_weights({"ZZZ": 50.0, "AAA": 50.0}, 1)
        assert weights == {"AAA": 1.0}

    def test_fewer_candidates_than_top_n(self) -> None:
        assert top_weights({"AAA": 50.0}, 5) == {"AAA": 1.0}

    def test_empty(self) -> None:
        assert top_weights({}, 5) == {}

    def test_invalid_top_n(self) -> None:
        with pytest.raises(ValueError, match="top_n"):
            top_weights({"AAA": 1.0}, 0)


def _data(dates: list[date], symbols: list[str]) -> BacktestData:
    bars = {
        s: [PriceBar(date=d, open=10.0, high=11.0, low=9.0, close=10.0) for d in dates]
        for s in symbols
    }
    return BacktestData(dates=dates, symbols=symbols, bars=bars)


class TestBuildStrategy:
    def test_returns_weights_only_on_scheduled_dates(self) -> None:
        dates = _dates(4)
        schedule = {dates[2]: {"AAA": 90.0, "BBB": 80.0}}
        strategy = build_strategy(schedule, top_n=1, universe={"AAA", "BBB"})
        ctx: dict[str, object] = {}
        assert strategy(_data(dates, ["AAA", "BBB"]), 0, ctx) == {}
        assert strategy(_data(dates, ["AAA", "BBB"]), 2, ctx) == {"AAA": 1.0}
        assert ctx["last_rebalance"] == dates[2].isoformat()

    def test_universe_filter_drops_unknown_symbols(self) -> None:
        dates = _dates(2)
        schedule = {dates[0]: {"AAA": 90.0, "OUTSIDE": 95.0}}
        strategy = build_strategy(schedule, top_n=2, universe={"AAA"})
        assert strategy(_data(dates, ["AAA"]), 0, {}) == {"AAA": 1.0}

    def test_empty_schedule_never_trades(self) -> None:
        dates = _dates(3)
        strategy = build_strategy({}, top_n=5, universe={"AAA"})
        assert all(strategy(_data(dates, ["AAA"]), i, {}) == {} for i in range(3))
