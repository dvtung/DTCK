"""Unit tests for the GĐ 4 strategy job (pure pieces + level arithmetic)."""

from __future__ import annotations

from datetime import date

import pytest

from src.quant.strategy.feature_engine import _rank_percentile, compute_group_scores
from src.quant.strategy.groups import PROFILES
from src.quant.strategy.job import _score_rows
from src.quant.strategy.recommend import atr, price_levels, trend_confirmed


class TestMidRankFix:
    def test_all_equal_values_score_midpoint_not_zero(self) -> None:
        """Regression: strictly-less-than collapsed binary features to 0.

        Live finding (2026-10-03): ``catalyst_event_ttm`` was 1.0 for every
        dividend payer and the strictly-less-than percentile returned 0 for all
        of them → ``grp:macro`` = 0 across the board. Mid-rank returns 50.
        """
        assert _rank_percentile(1.0, [1.0, 1.0, 1.0]) == 50.0
        assert _rank_percentile(0.0, [0.0, 0.0]) == 50.0

    def test_extremes_are_ordered(self) -> None:
        dist = [10.0, 20.0, 30.0]
        assert _rank_percentile(10.0, dist) < _rank_percentile(30.0, dist)
        assert _rank_percentile(40.0, dist) == 100.0

    def test_binary_feature_no_longer_collapses_group_macro(self) -> None:
        raw = {
            "A": {"catalyst_event_ttm": 1.0},
            "B": {"catalyst_event_ttm": 1.0},
            "C": {"catalyst_event_ttm": 0.0},
        }
        results = {(r.symbol, r.group): r for r in compute_group_scores(raw)}
        # mid-rank: for 1.0 → (1 below + 0.5×2 tied)/3 = 2/3 → 66.67
        assert results[("A", "macro")].score == pytest.approx(66.6667, abs=1e-3)
        assert results[("A", "macro")].score == results[("B", "macro")].score
        # for 0.0 → (0 + 0.5×1)/3 = 1/6 → 16.67
        assert results[("C", "macro")].score == pytest.approx(16.6667, abs=1e-3)
        # All-equal universe is the midpoint — the original bug returned 0.
        assert _rank_percentile(1.0, [1.0, 1.0]) == 50.0

    def test_empty_distribution_is_zero(self) -> None:
        assert _rank_percentile(1.0, []) == 0.0


class TestPriceLevels:
    def test_atr_is_close_to_close_average_range(self) -> None:
        closes = [100.0, 104.0, 101.0, 103.0]  # ranges 4,3,2 → ATR(3)=3.0
        assert atr(closes, period=3) == 3.0
        assert atr([100.0, 100.0], period=20) is None  # not enough bars

    def test_levels_are_deterministic_and_ordered(self) -> None:
        # 25 bars so the default ATR(20) window is available.
        closes = ([100.0, 102.0, 99.0, 101.0, 103.0, 102.0] * 5)[:24] + [104.0]
        levels = price_levels(closes)
        assert levels.buy_zone_low is not None
        assert levels.buy_zone_high is not None
        assert levels.stop_loss is not None
        assert levels.target_price is not None
        assert levels.rr_ratio is not None
        # Stop below the buy zone, target above it, R/R = 3·ATR / 2·ATR = 1.5.
        assert levels.buy_zone_low < levels.buy_zone_high
        assert levels.stop_loss < levels.buy_zone_low
        assert levels.target_price > levels.buy_zone_high
        assert levels.rr_ratio == pytest.approx(1.5)

    def test_unknown_levels_without_history(self) -> None:
        levels = price_levels([])
        assert levels.buy_zone_low is None
        assert levels.rr_ratio is None


class TestTrendConfirmation:
    def test_uptrend_confirmed(self) -> None:
        closes = [100.0 + i for i in range(120)]  # rising → close > SMA20 > SMA50
        assert trend_confirmed(closes) is True

    def test_downtrend_not_confirmed(self) -> None:
        closes = [200.0 - i for i in range(120)]
        assert trend_confirmed(closes) is False

    def test_short_history_is_not_confirmed(self) -> None:
        """Missing evidence must never upgrade a grade (§31)."""
        assert trend_confirmed([100.0, 101.0]) is False


class TestScoreRows:
    def _groups(self) -> dict[str, dict[str, float | None]]:
        from src.quant.strategy.groups import GROUPS

        base = {g: 50.0 for g in GROUPS}
        return {"AAA": dict(base), "BBB": dict(base)}

    def test_writes_one_row_per_profile_and_symbol(self) -> None:
        closes = {"AAA": tuple(float(i) for i in range(1, 130)), "BBB": (1.0, 2.0)}
        scores, recs, scored, skipped = _score_rows(
            date(2026, 10, 3), self._groups(), closes
        )
        assert scored == len(PROFILES) * 2
        assert skipped == 0
        assert {r["strategy"] for r in scores} == set(PROFILES)
        assert len(recs) == len(scores)

    def test_symbol_without_prices_is_skipped(self) -> None:
        scores, recs, scored, skipped = _score_rows(
            date(2026, 10, 3), {"AAA": dict(self._groups()["AAA"])}, {"AAA": ()}
        )
        assert scores == []
        assert recs == []
        assert scored == 0
        assert skipped == 1

    def test_short_profile_rows_carry_trend_gate(self) -> None:
        closes = {"AAA": tuple(float(i) for i in range(1, 130))}
        _, recs, _, _ = _score_rows(date(2026, 10, 3), {"AAA": {}}, closes)
        # An empty group dict means no overall score → nothing is written.
        assert recs == []
