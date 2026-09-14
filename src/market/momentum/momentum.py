"""Momentum indicators (spec §11.4, QUANT_ENGINE.md §2.4).

Pure-Python deterministic calculations.
"""

from __future__ import annotations


def return_n(close: list[float], n: int) -> list[float | None]:
    """N-day return: (close[i] - close[i-n]) / close[i-n].

    Returns ``None`` for the first ``n`` positions.
    """
    if n <= 0:
        raise ValueError(f"n must be > 0, got {n}")
    result: list[float | None] = []
    for i in range(len(close)):
        if i < n or close[i - n] == 0:
            result.append(None)
        else:
            result.append((close[i] - close[i - n]) / close[i - n])
    return result


def returns_multi(
    close: list[float],
    periods: list[int],
) -> dict[int, list[float | None]]:
    """Compute returns for multiple periods at once.

    Returns a dict mapping each period to its return series.
    """
    return {n: return_n(close, n) for n in periods}


def volume_expansion(
    volume: list[int],
    period: int = 20,
) -> list[float | None]:
    """Volume expansion ratio: volume[i] / SMA(volume, period).

    Values > 1 indicate above-average volume. Returns ``None`` during warmup.
    """
    if period <= 0:
        raise ValueError(f"period must be > 0, got {period}")
    result: list[float | None] = []
    for i in range(len(volume)):
        if i < period - 1:
            result.append(None)
        else:
            window = volume[i - period + 1 : i + 1]
            avg = sum(window) / period
            if avg == 0:
                result.append(None)
            else:
                result.append(volume[i] / avg)
    return result


def relative_momentum(
    close: list[float],
    benchmark_close: list[float],
    n: int,
) -> list[float | None]:
    """Relative momentum vs benchmark over n periods.

    = stock_return_n / benchmark_return_n (both computed over same window).
    Returns ``None`` during warmup or when benchmark return is zero.
    """
    if len(close) != len(benchmark_close):
        raise ValueError("close and benchmark_close must have the same length")
    stock_returns = return_n(close, n)
    bench_returns = return_n(benchmark_close, n)

    result: list[float | None] = []
    for sr, br in zip(stock_returns, bench_returns, strict=True):
        if sr is None or br is None or br == 0:
            result.append(None)
        else:
            result.append(sr / br)
    return result


__all__ = [
    "return_n",
    "returns_multi",
    "volume_expansion",
    "relative_momentum",
]
