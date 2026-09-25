"""Scoring job: price-derived raw factors (W1b).

The job only extracts *raw* values; ranking/renormalization belongs to
``src/quant/factors/scoring.py`` (covered by ``test_quant_scoring.py``). These
tests pin the extraction: which dimensions are available, that unavailable ones
are ``None`` (never a placeholder), and that risk is sign-flipped.
"""

from __future__ import annotations

import pytest

from src.market.momentum import momentum
from src.quant.scoring.job import (
    MOMENTUM_PERIOD,
    RSI_PERIOD,
    raw_price_factors,
)

RISING = [100.0 + i * 0.5 for i in range(80)]
OSCILLATING = [100.0 + (i % 7) - 3 for i in range(80)]


def test_short_history_yields_no_factor_instead_of_a_guess() -> None:
    assert raw_price_factors([100.0, 101.0]) == {
        "technical": None,
        "momentum": None,
        "risk": None,
    }


def test_empty_history_is_safe() -> None:
    assert raw_price_factors([]) == {"technical": None, "momentum": None, "risk": None}


def test_dimensions_are_exactly_the_price_derived_ones() -> None:
    raw = raw_price_factors(OSCILLATING)
    # fundamental/valuation/quality need statements we do not have yet (§12) —
    # they must not appear as fabricated values.
    assert set(raw) == {"technical", "momentum", "risk"}
    assert all(value is not None for value in raw.values())


def test_rsi_is_100_on_a_monotonically_rising_series() -> None:
    raw = raw_price_factors(RISING)
    assert raw["technical"] == pytest.approx(100.0)


def test_momentum_matches_the_shared_engine() -> None:
    expected = momentum.return_n(RISING, MOMENTUM_PERIOD)[-1]
    assert raw_price_factors(RISING)["momentum"] == pytest.approx(expected)


def test_risk_is_negated_volatility_so_higher_is_safer() -> None:
    raw = raw_price_factors(OSCILLATING)
    assert raw["risk"] is not None
    assert raw["risk"] < 0.0  # a moving series always has positive volatility
    # A flat series has zero volatility, hence zero (best) risk.
    flat = raw_price_factors([100.0] * 80)
    assert flat["risk"] == pytest.approx(0.0)
    assert flat["technical"] is not None


def test_rsi_period_boundary() -> None:
    """RSI needs ``RSI_PERIOD + 1`` closes; one fewer must yield ``None``."""
    assert raw_price_factors(RISING[: RSI_PERIOD + 1])["technical"] is not None
    assert raw_price_factors(RISING[:RSI_PERIOD])["technical"] is None
