"""Expected-value tests for T006 technical indicators (spec §38, QUANT_ENGINE.md §2.1).

Each indicator is validated against hand-computed expected values.
"""

from __future__ import annotations

import pytest

from src.market.technical import (
    atr,
    bollinger_bands,
    ema,
    macd,
    obv,
    relative_strength,
    rsi,
    sma,
    volume_sma,
)

# --------------------------------------------------------------------------- #
#  SMA
# --------------------------------------------------------------------------- #


class TestSMA:
    def test_period_3(self):
        result = sma([1, 2, 3, 4, 5], 3)
        assert result == [None, None, 2.0, 3.0, 4.0]

    def test_period_1_equals_input(self):
        result = sma([10, 20, 30], 1)
        assert result == [10.0, 20.0, 30.0]

    def test_period_equals_length(self):
        result = sma([1, 2, 3, 4], 4)
        assert result == [None, None, None, 2.5]

    def test_period_longer_than_data(self):
        result = sma([1, 2], 5)
        assert result == [None, None]

    def test_empty_list(self):
        assert sma([], 3) == []

    def test_invalid_period(self):
        with pytest.raises(ValueError, match="period must be > 0"):
            sma([1, 2, 3], 0)

    def test_constant_values(self):
        result = sma([5, 5, 5, 5], 2)
        assert result == [None, 5.0, 5.0, 5.0]


# --------------------------------------------------------------------------- #
#  EMA
# --------------------------------------------------------------------------- #


class TestEMA:
    def test_period_3(self):
        result = ema([1, 2, 3, 4, 5], 3)
        assert result[0] is None
        assert result[1] is None
        assert result[2] == 2.0
        assert result[3] == 3.0
        assert result[4] == 4.0

    def test_period_1(self):
        result = ema([10, 20, 30], 1)
        assert result == [10.0, 20.0, 30.0]

    def test_constant_values(self):
        result = ema([5, 5, 5, 5, 5], 3)
        assert all(v == 5.0 for v in result if v is not None)

    def test_data_shorter_than_period(self):
        result = ema([1, 2], 5)
        assert result == [None, None]

    def test_invalid_period(self):
        with pytest.raises(ValueError, match="period must be > 0"):
            ema([1, 2, 3], 0)

    def test_seed_is_sma(self):
        result = ema([1, 2, 3], 2)
        assert result[1] == 1.5
        assert result[2] == 2.5


# --------------------------------------------------------------------------- #
#  RSI
# --------------------------------------------------------------------------- #


class TestRSI:
    def test_all_gains(self):
        close = [100 + i for i in range(15)]
        result = rsi(close, 14)
        assert result[14] == 100.0

    def test_all_losses(self):
        close = [100 - i for i in range(15)]
        result = rsi(close, 14)
        assert result[14] == 0.0

    def test_mixed_gains_losses(self):
        close = [10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10]
        result = rsi(close, 14)
        assert result[14] == 50.0

    def test_insufficient_data(self):
        result = rsi([1, 2, 3], 14)
        assert result == [None, None, None]

    def test_invalid_period(self):
        with pytest.raises(ValueError, match="period must be > 0"):
            rsi([1, 2, 3], 0)

    def test_flat_prices(self):
        close = [10] * 20
        result = rsi(close, 14)
        assert result[14] == 100.0


# --------------------------------------------------------------------------- #
#  MACD
# --------------------------------------------------------------------------- #


class TestMACD:
    def test_returns_three_lists(self):
        close = [100 + i for i in range(40)]
        line, signal, hist = macd(close)
        assert len(line) == 40
        assert len(signal) == 40
        assert len(hist) == 40

    def test_macd_line_starts_at_slow_minus_1(self):
        close = [100 + i for i in range(40)]
        line, signal, hist = macd(close, fast=12, slow=26, signal=9)
        assert line[24] is None
        assert line[25] is not None

    def test_histogram_is_difference(self):
        close = [100 + i for i in range(40)]
        line, signal, hist = macd(close)
        for i in range(len(close)):
            if line[i] is not None and signal[i] is not None:
                assert hist[i] == pytest.approx(line[i] - signal[i], abs=1e-10)

    def test_invalid_fast_slow(self):
        with pytest.raises(ValueError, match="fast .* must be < slow"):
            macd([1, 2, 3], fast=26, slow=12)


# --------------------------------------------------------------------------- #
#  Bollinger Bands
# --------------------------------------------------------------------------- #


class TestBollingerBands:
    def test_period_3(self):
        upper, middle, lower = bollinger_bands([1, 2, 3, 4, 5], period=3, num_std=2)
        assert middle == [None, None, 2.0, 3.0, 4.0]
        assert upper[0] is None
        assert lower[0] is None
        expected_std = (2 / 3) ** 0.5
        assert upper[2] == pytest.approx(2.0 + 2 * expected_std, abs=1e-10)
        assert lower[2] == pytest.approx(2.0 - 2 * expected_std, abs=1e-10)

    def test_constant_values_bands_collapse(self):
        upper, middle, lower = bollinger_bands([5, 5, 5, 5, 5], period=3)
        for i in range(2, 5):
            assert upper[i] == 5.0
            assert lower[i] == 5.0

    def test_invalid_period(self):
        with pytest.raises(ValueError, match="period must be > 0"):
            bollinger_bands([1, 2, 3], period=0)


# --------------------------------------------------------------------------- #
#  ATR
# --------------------------------------------------------------------------- #


class TestATR:
    def test_basic(self):
        high = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24]
        low = [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22]
        close = [9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23]
        result = atr(high, low, close, period=14)
        assert result[13] == 2.0
        assert result[14] == 2.0

    def test_with_gaps(self):
        high = [12, 11, 10]
        low = [10, 9, 8]
        close = [10, 10, 10]
        result = atr(high, low, close, period=2)
        assert result[1] == 2.0

    def test_mismatched_lengths(self):
        with pytest.raises(ValueError, match="same length"):
            atr([1, 2], [1], [1, 2], period=2)

    def test_single_bar(self):
        result = atr([10], [8], [9], period=14)
        assert result == [None]


# --------------------------------------------------------------------------- #
#  OBV
# --------------------------------------------------------------------------- #


class TestOBV:
    def test_rising_close(self):
        result = obv([1, 2, 3, 4], [100, 200, 300, 400])
        assert result == [100, 300, 600, 1000]

    def test_falling_close(self):
        result = obv([4, 3, 2, 1], [100, 200, 300, 400])
        assert result == [100, -100, -400, -800]

    def test_flat_close(self):
        result = obv([5, 5, 5], [100, 200, 300])
        assert result == [100, 100, 100]

    def test_mixed(self):
        result = obv([1, 2, 2, 1], [100, 200, 300, 400])
        assert result == [100, 300, 300, -100]

    def test_empty(self):
        assert obv([], []) == []

    def test_mismatched_lengths(self):
        with pytest.raises(ValueError, match="same length"):
            obv([1, 2], [100])


# --------------------------------------------------------------------------- #
#  Volume SMA
# --------------------------------------------------------------------------- #


class TestVolumeSMA:
    def test_basic(self):
        result = volume_sma([100, 200, 300, 400, 500], period=3)
        assert result == [None, None, 200.0, 300.0, 400.0]


# --------------------------------------------------------------------------- #
#  Relative Strength
# --------------------------------------------------------------------------- #


class TestRelativeStrength:
    def test_basic(self):
        result = relative_strength([100, 200, 300], [10, 20, 30])
        assert result == [10.0, 10.0, 10.0]

    def test_zero_benchmark(self):
        result = relative_strength([100, 200], [0, 10])
        assert result[0] is None
        assert result[1] == 20.0

    def test_mismatched_lengths(self):
        with pytest.raises(ValueError, match="same length"):
            relative_strength([1, 2], [1])
