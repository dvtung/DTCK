"""Risk indicators (spec §11.5, QUANT_ENGINE.md §2.5).

Pure-Python deterministic calculations.
"""

from __future__ import annotations

import math


def volatility(
    close: list[float],
    period: int = 20,
    annualize: bool = True,
) -> list[float | None]:
    """Rolling annualized volatility from log returns.

    Computes standard deviation of log(close[i]/close[i-1]) over the window,
    then annualizes by multiplying by sqrt(252).

    Returns ``None`` for the first ``period`` positions.
    """
    if period <= 0:
        raise ValueError(f"period must be > 0, got {period}")

    # Compute log returns
    log_returns: list[float] = []
    for i in range(1, len(close)):
        if close[i - 1] <= 0 or close[i] <= 0:
            log_returns.append(float("nan"))
        else:
            log_returns.append(math.log(close[i] / close[i - 1]))

    result: list[float | None] = [None]  # first price has no return

    for i in range(len(log_returns)):
        if i < period - 1:
            result.append(None)
        else:
            window = log_returns[i - period + 1 : i + 1]
            valid = [r for r in window if not math.isnan(r)]
            if len(valid) < 2:
                result.append(None)
            else:
                mean = sum(valid) / len(valid)
                variance = sum((r - mean) ** 2 for r in valid) / (len(valid) - 1)
                std = math.sqrt(variance)
                if annualize:
                    std *= math.sqrt(252)
                result.append(std)

    return result


def beta(
    stock_returns: list[float],
    market_returns: list[float],
    period: int = 60,
) -> list[float | None]:
    """Rolling beta = cov(stock, market) / var(market).

    Returns ``None`` during warmup or when market variance is zero.
    """
    if len(stock_returns) != len(market_returns):
        raise ValueError("stock_returns and market_returns must have the same length")
    if period <= 0:
        raise ValueError(f"period must be > 0, got {period}")

    result: list[float | None] = []
    for i in range(len(stock_returns)):
        if i < period - 1:
            result.append(None)
        else:
            sr_window = stock_returns[i - period + 1 : i + 1]
            mr_window = market_returns[i - period + 1 : i + 1]
            # Filter out NaN pairs
            pairs = [(s, m) for s, m in zip(sr_window, mr_window, strict=True)
                     if not (math.isnan(s) or math.isnan(m))]
            if len(pairs) < 2:
                result.append(None)
                continue
            sr_clean, mr_clean = zip(*pairs, strict=True)
            mean_s = sum(sr_clean) / len(sr_clean)
            mean_m = sum(mr_clean) / len(mr_clean)
            cov = sum(
                (s - mean_s) * (m - mean_m)
                for s, m in zip(sr_clean, mr_clean, strict=True)
            ) / (len(pairs) - 1)
            var_m = sum((m - mean_m) ** 2 for m in mr_clean) / (len(pairs) - 1)
            if var_m == 0:
                result.append(None)
            else:
                result.append(cov / var_m)
    return result


def max_drawdown(close: list[float]) -> list[float | None]:
    """Trailing maximum drawdown from peak.

    At each position, computes the worst drawdown from any prior peak.
    Returns negative values (e.g., -0.25 = 25% drawdown).
    First position returns None (no prior data).
    """
    if len(close) < 2:
        return [None] * len(close)

    result: list[float | None] = [None]
    peak = close[0]
    max_dd = 0.0

    for i in range(1, len(close)):
        if close[i] > peak:
            peak = close[i]
        dd = (close[i] - peak) / peak if peak != 0 else 0.0
        if dd < max_dd:
            max_dd = dd
        result.append(max_dd)

    return result


def liquidity(adv: float, float_shares: float) -> float | None:
    """Liquidity ratio = average daily value / float_shares.

    Higher = more liquid. Returns ``None`` if float_shares is zero.
    """
    if float_shares == 0:
        return None
    return adv / float_shares


def gap_risk(
    close: list[float],
    open_: list[float],
    period: int = 20,
) -> list[float | None]:
    """Open-gap frequency: fraction of days with a gap > 1%.

    A gap occurs when |open[i] / close[i-1] - 1| > 0.01.
    Returns ``None`` for the first ``period`` positions.
    """
    if len(close) != len(open_):
        raise ValueError("close and open_ must have the same length")
    if period <= 0:
        raise ValueError(f"period must be > 0, got {period}")

    result: list[float | None] = []
    for i in range(len(close)):
        if i < period or i == 0:
            result.append(None)
        else:
            window_close = close[i - period + 1 : i + 1]
            window_open = open_[i - period + 1 : i + 1]
            gaps = 0
            for j in range(1, len(window_close)):
                prev_close = window_close[j - 1]
                curr_open = window_open[j]
                if prev_close != 0 and abs(curr_open / prev_close - 1) > 0.01:
                    gaps += 1
            result.append(gaps / (len(window_close) - 1))

    return result


def debt_risk(debt_to_equity: float) -> float:
    """Debt risk score (0-1, higher = riskier).

    Maps D/E to a simple risk score:
    - D/E < 0.5: low risk (0.0)
    - 0.5 <= D/E < 1.0: moderate (0.33)
    - 1.0 <= D/E < 2.0: high (0.67)
    - D/E >= 2.0: very high (1.0)
    """
    if debt_to_equity < 0.5:
        return 0.0
    elif debt_to_equity < 1.0:
        return 0.33
    elif debt_to_equity < 2.0:
        return 0.67
    else:
        return 1.0


__all__ = [
    "volatility",
    "beta",
    "max_drawdown",
    "liquidity",
    "gap_risk",
    "debt_risk",
]
