"""Valuation ratios (spec §11.3, QUANT_ENGINE.md §2.3).

Pure-Python deterministic calculations. All functions return ``None`` for
invalid inputs (zero denominator, negative prices).
"""

from __future__ import annotations


def pe(price: float, eps: float) -> float | None:
    """Price-to-earnings ratio = price / eps."""
    if eps <= 0:
        return None
    return price / eps


def forward_pe(price: float, forward_eps: float) -> float | None:
    """Forward P/E = price / forward_eps."""
    if forward_eps <= 0:
        return None
    return price / forward_eps


def pb(price: float, book_value_per_share: float) -> float | None:
    """Price-to-book ratio = price / book_value_per_share."""
    if book_value_per_share <= 0:
        return None
    return price / book_value_per_share


def ev_ebitda(enterprise_value: float, ebitda: float) -> float | None:
    """EV/EBITDA = enterprise_value / ebitda."""
    if ebitda <= 0:
        return None
    return enterprise_value / ebitda


def ev_sales(enterprise_value: float, revenue: float) -> float | None:
    """EV/Sales = enterprise_value / revenue."""
    if revenue <= 0:
        return None
    return enterprise_value / revenue


def dividend_yield(dividend_per_share: float, price: float) -> float | None:
    """Dividend yield = dividend_per_share / price."""
    if price <= 0:
        return None
    return dividend_per_share / price


def peg(pe_ratio: float, earnings_growth_pct: float) -> float | None:
    """PEG ratio = pe / earnings_growth_percent.

    ``earnings_growth_pct`` is in percentage points (e.g., 15.0 for 15%).
    """
    if earnings_growth_pct <= 0:
        return None
    return pe_ratio / earnings_growth_pct


def enterprise_value(market_cap: float, total_debt: float, cash: float) -> float:
    """Enterprise value = market_cap + total_debt - cash."""
    return market_cap + total_debt - cash


def percentile_rank(value: float, distribution: list[float]) -> float | None:
    """Percentile rank of ``value`` within ``distribution`` (0-100).

    Uses the "strictly less than" definition: percentage of values below.
    Returns ``None`` if distribution is empty.
    """
    if not distribution:
        return None
    below = sum(1 for x in distribution if x < value)
    return (below / len(distribution)) * 100


def industry_percentile(
    value: float,
    industry_values: list[float],
) -> float | None:
    """Percentile rank within an industry (0-100).

    Convenience wrapper around ``percentile_rank`` for industry comparison.
    """
    return percentile_rank(value, industry_values)


def historical_percentile(
    value: float,
    historical_values: list[float],
) -> float | None:
    """Percentile rank vs own history (0-100).

    Convenience wrapper around ``percentile_rank`` for historical comparison.
    """
    return percentile_rank(value, historical_values)


__all__ = [
    "pe",
    "forward_pe",
    "pb",
    "ev_ebitda",
    "ev_sales",
    "dividend_yield",
    "peg",
    "enterprise_value",
    "percentile_rank",
    "industry_percentile",
    "historical_percentile",
]
