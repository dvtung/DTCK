"""Collectors (T004): pull raw records from a provider for a dataset.

Collectors are thin and side-effect free — validation, normalization, persistence
and quality scoring happen in ``pipelines`` (see ``docs/DATA_ARCHITECTURE.md`` §2).
"""

from __future__ import annotations

from datetime import date, datetime

from src.data.providers.base import DataProvider
from src.data.records import EODBar, EventRow, FinancialRow, IndexBar, MacroPoint, NewsItem


def collect_eod(provider: DataProvider, symbols: list[str], start: date, end: date) -> list[EODBar]:
    """Collect raw EOD bars for ``symbols`` in ``[start, end]``."""
    if not provider.supports("prices"):
        raise ValueError(f"provider '{provider.id}' does not support dataset 'prices'")
    return provider.fetch_eod(sorted({s.upper() for s in symbols}), start, end)


def collect_index(
    provider: DataProvider, index_codes: list[str], start: date, end: date
) -> list[IndexBar]:
    """Collect raw index bars for ``index_codes`` in ``[start, end]``."""
    if not provider.supports("index_prices"):
        raise ValueError(f"provider '{provider.id}' does not support dataset 'index_prices'")
    return provider.fetch_index(sorted({c.upper() for c in index_codes}), start, end)


def collect_news(provider: DataProvider, since: datetime) -> list[NewsItem]:
    """Collect raw news items published after ``since``."""
    if not provider.supports("news"):
        raise ValueError(f"provider '{provider.id}' does not support dataset 'news'")
    return provider.fetch_news(since)


def collect_financials(
    provider: DataProvider,
    symbols: list[str],
    *,
    period_types: tuple[str, ...] = ("QUARTER", "YEAR"),
) -> list[FinancialRow]:
    """Collect raw financial-statement line items for ``symbols``."""
    if not provider.supports("financials"):
        raise ValueError(f"provider '{provider.id}' does not support dataset 'financials'")
    return provider.fetch_financials(
        sorted({s.upper() for s in symbols}), period_types=period_types
    )


def collect_events(provider: DataProvider, symbols: list[str], *, since: date) -> list[EventRow]:
    """Collect raw corporate events on/after ``since`` for ``symbols``."""
    if not provider.supports("events"):
        raise ValueError(f"provider '{provider.id}' does not support dataset 'events'")
    return provider.fetch_events(sorted({s.upper() for s in symbols}), since=since)


def collect_macro(
    provider: DataProvider,
    indicators: list[str],
    *,
    start: date,
    end: date,
) -> list[MacroPoint]:
    """Collect macro series observations in ``[start, end]``."""
    if not provider.supports("macro"):
        raise ValueError(f"provider '{provider.id}' does not support dataset 'macro'")
    return provider.fetch_macro(indicators, start=start, end=end)


__all__ = [
    "collect_eod",
    "collect_events",
    "collect_financials",
    "collect_index",
    "collect_macro",
    "collect_news",
]
