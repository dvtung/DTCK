"""Technical indicators (spec §11.1, QUANT_ENGINE.md §2.1).

Pure-Python, deterministic implementations. Each function accepts a list of
float values and returns a list of ``float | None`` where ``None`` marks the
warmup period (insufficient data).

No numpy/pandas dependency for the MVP — VN30 is 30 stocks, and pure Python
keeps the expected-value tests (§38) exact and dependency-free.
"""

from __future__ import annotations


def sma(close: list[float], period: int) -> list[float | None]:
    """Simple Moving Average.

    ``close[i]`` contributes to the average of the window ending at ``i``.
    Returns ``None`` for the first ``period - 1`` positions.
    """
    if period <= 0:
        raise ValueError(f"period must be > 0, got {period}")
    result: list[float | None] = []
    for i in range(len(close)):
        if i < period - 1:
            result.append(None)
        else:
            window = close[i - period + 1 : i + 1]
            result.append(sum(window) / period)
    return result


def ema(close: list[float], period: int) -> list[float | None]:
    """Exponential Moving Average.

    Seeded with the SMA of the first ``period`` values, then applies the
    standard EMA recurrence with multiplier ``2 / (period + 1)``.
    Returns ``None`` for the first ``period - 1`` positions.
    """
    if period <= 0:
        raise ValueError(f"period must be > 0, got {period}")
    if len(close) < period:
        return [None] * len(close)

    multiplier = 2.0 / (period + 1)
    result: list[float | None] = [None] * (period - 1)

    # Seed with SMA of first `period` values
    seed = sum(close[:period]) / period
    result.append(seed)

    for i in range(period, len(close)):
        prev = result[i - 1]
        assert prev is not None
        value = (close[i] - prev) * multiplier + prev
        result.append(value)

    return result


def rsi(close: list[float], period: int = 14) -> list[float | None]:
    """Relative Strength Index (Wilder's smoothing).

    Returns ``None`` for the first ``period`` positions (``period`` deltas
    require ``period + 1`` data points).
    """
    if period <= 0:
        raise ValueError(f"period must be > 0, got {period}")
    if len(close) <= period:
        return [None] * len(close)

    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(close)):
        delta = close[i] - close[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    # First `period` positions are None (need `period` deltas = `period + 1` prices)
    result: list[float | None] = [None] * period

    # First average: simple average of first `period` deltas
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    if avg_loss == 0:
        result.append(100.0)
    else:
        rs = avg_gain / avg_loss
        result.append(100.0 - 100.0 / (1.0 + rs))

    # Subsequent values: Wilder's smoothing
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            result.append(100.0)
        else:
            rs = avg_gain / avg_loss
            result.append(100.0 - 100.0 / (1.0 + rs))

    # Pad remaining positions (shouldn't happen, but safety)
    while len(result) < len(close):
        result.append(None)

    return result


def macd(
    close: list[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """MACD: line, signal, histogram.

    Returns three lists of ``float | None``. The MACD line starts at index
    ``slow - 1``; the signal line starts at ``slow + signal - 2``; the
    histogram is ``line - signal`` where both are defined.
    """
    if fast >= slow:
        raise ValueError(f"fast ({fast}) must be < slow ({slow})")

    fast_ema = ema(close, fast)
    slow_ema = ema(close, slow)

    # MACD line = fast EMA - slow EMA
    macd_line: list[float | None] = []
    for i in range(len(close)):
        f = fast_ema[i]
        s = slow_ema[i]
        if f is not None and s is not None:
            macd_line.append(f - s)
        else:
            macd_line.append(None)

    # Signal line = EMA of MACD line (skip None values)
    macd_values = [v for v in macd_line if v is not None]
    signal_ema_values = ema(macd_values, signal)

    # Map signal EMA back to original indices
    signal_line: list[float | None] = [None] * len(close)
    signal_idx = 0
    for i in range(len(close)):
        if macd_line[i] is not None:
            if signal_idx < len(signal_ema_values):
                signal_line[i] = signal_ema_values[signal_idx]
            signal_idx += 1

    # Histogram = MACD - signal
    histogram: list[float | None] = []
    for i in range(len(close)):
        m = macd_line[i]
        s = signal_line[i]
        if m is not None and s is not None:
            histogram.append(m - s)
        else:
            histogram.append(None)

    return macd_line, signal_line, histogram


def bollinger_bands(
    close: list[float],
    period: int = 20,
    num_std: float = 2.0,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Bollinger Bands: upper, middle (SMA), lower.

    Uses population standard deviation (not sample) of the window.
    Returns ``None`` for the first ``period - 1`` positions.
    """
    if period <= 0:
        raise ValueError(f"period must be > 0, got {period}")

    middle = sma(close, period)
    upper: list[float | None] = []
    lower: list[float | None] = []

    for i in range(len(close)):
        if middle[i] is None:
            upper.append(None)
            lower.append(None)
        else:
            window = close[i - period + 1 : i + 1]
            mean = middle[i]
            assert mean is not None
            variance = sum((x - mean) ** 2 for x in window) / period
            std = variance**0.5
            upper.append(mean + num_std * std)
            lower.append(mean - num_std * std)

    return upper, middle, lower


def atr(
    high: list[float],
    low: list[float],
    close: list[float],
    period: int = 14,
) -> list[float | None]:
    """Average True Range (Wilder's smoothing).

    Returns ``None`` for the first ``period`` positions.
    """
    if len(high) != len(low) or len(high) != len(close):
        raise ValueError("high, low, close must have the same length")
    if len(close) < 2:
        return [None] * len(close)

    # True Range series
    tr: list[float] = [high[0] - low[0]]  # first TR = high - low
    for i in range(1, len(close)):
        tr.append(
            max(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i] - close[i - 1]),
            )
        )

    result: list[float | None] = []

    # First ATR: simple average of first `period` TR values
    if len(tr) < period:
        return [None] * len(close)

    atr_val = sum(tr[:period]) / period
    result = [None] * (period - 1)
    result.append(atr_val)

    # Subsequent: Wilder's smoothing
    for i in range(period, len(tr)):
        atr_val = (atr_val * (period - 1) + tr[i]) / period
        result.append(atr_val)

    return result


def obv(close: list[float], volume: list[int]) -> list[int]:
    """On-Balance Volume.

    Running sum: volume added when close rises, subtracted when close falls,
    unchanged when close is flat. First OBV = first volume.
    """
    if len(close) != len(volume):
        raise ValueError("close and volume must have the same length")
    if not close:
        return []

    result: list[int] = [volume[0]]
    for i in range(1, len(close)):
        if close[i] > close[i - 1]:
            result.append(result[-1] + volume[i])
        elif close[i] < close[i - 1]:
            result.append(result[-1] - volume[i])
        else:
            result.append(result[-1])
    return result


def volume_sma(volume: list[int], period: int = 20) -> list[float | None]:
    """Volume Simple Moving Average."""
    return sma([float(v) for v in volume], period)


def relative_strength(
    close: list[float],
    benchmark_close: list[float],
) -> list[float | None]:
    """Relative strength vs a benchmark (e.g., VNINDEX).

    Returns the ratio ``close / benchmark`` at each position. ``None`` if
    benchmark is zero.
    """
    if len(close) != len(benchmark_close):
        raise ValueError("close and benchmark_close must have the same length")

    result: list[float | None] = []
    for c, b in zip(close, benchmark_close, strict=True):
        if b == 0:
            result.append(None)
        else:
            result.append(c / b)
    return result


__all__ = [
    "sma",
    "ema",
    "rsi",
    "macd",
    "bollinger_bands",
    "atr",
    "obv",
    "volume_sma",
    "relative_strength",
]
