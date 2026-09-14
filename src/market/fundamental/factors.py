"""Fundamental factors (spec §11.2, QUANT_ENGINE.md §2.2).

Pure-Python deterministic calculations from financial statement data.
Each function is side-effect free and tested against expected values.
"""

from __future__ import annotations


def revenue_growth(revenue: list[float]) -> list[float | None]:
    """Year-over-year revenue growth.

    Returns ``None`` for the first position (no prior period).
    """
    if len(revenue) < 2:
        return [None] * len(revenue)
    result: list[float | None] = [None]
    for i in range(1, len(revenue)):
        if revenue[i - 1] == 0:
            result.append(None)
        else:
            result.append((revenue[i] - revenue[i - 1]) / abs(revenue[i - 1]))
    return result


def eps_growth(eps: list[float]) -> list[float | None]:
    """Year-over-year EPS growth.

    Returns ``None`` for the first position.
    """
    if len(eps) < 2:
        return [None] * len(eps)
    result: list[float | None] = [None]
    for i in range(1, len(eps)):
        if eps[i - 1] == 0:
            result.append(None)
        else:
            result.append((eps[i] - eps[i - 1]) / abs(eps[i - 1]))
    return result


def roe(net_income: float, equity: float) -> float | None:
    """Return on Equity = net_income / equity."""
    if equity == 0:
        return None
    return net_income / equity


def roa(net_income: float, assets: float) -> float | None:
    """Return on Assets = net_income / assets."""
    if assets == 0:
        return None
    return net_income / assets


def gross_margin(gross_profit: float, revenue: float) -> float | None:
    """Gross margin = gross_profit / revenue."""
    if revenue == 0:
        return None
    return gross_profit / revenue


def operating_margin(operating_income: float, revenue: float) -> float | None:
    """Operating margin = operating_income / revenue."""
    if revenue == 0:
        return None
    return operating_income / revenue


def net_margin(net_income: float, revenue: float) -> float | None:
    """Net margin = net_income / revenue."""
    if revenue == 0:
        return None
    return net_income / revenue


def debt_to_equity(total_debt: float, equity: float) -> float | None:
    """Debt-to-equity ratio = total_debt / equity."""
    if equity == 0:
        return None
    return total_debt / equity


def interest_coverage(operating_income: float, interest_expense: float) -> float | None:
    """Interest coverage ratio = operating_income / interest_expense."""
    if interest_expense == 0:
        return float("inf") if operating_income > 0 else None
    return operating_income / interest_expense


def free_cash_flow(operating_cash_flow: float, capex: float) -> float:
    """Free cash flow = operating_cash_flow - capex."""
    return operating_cash_flow - capex


def fcf_margin(fcf: float, revenue: float) -> float | None:
    """FCF margin = free_cash_flow / revenue."""
    if revenue == 0:
        return None
    return fcf / revenue


def earnings_quality(net_income: float, operating_cash_flow: float) -> float | None:
    """Earnings quality proxy = operating_cash_flow / net_income.

    Values > 1 suggest high-quality earnings (cash-backed).
    Returns ``None`` when net_income is 0.
    """
    if net_income == 0:
        return None
    return operating_cash_flow / net_income


__all__ = [
    "revenue_growth",
    "eps_growth",
    "roe",
    "roa",
    "gross_margin",
    "operating_margin",
    "net_margin",
    "debt_to_equity",
    "interest_coverage",
    "free_cash_flow",
    "fcf_margin",
    "earnings_quality",
]
