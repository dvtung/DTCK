"""Collectors (T004): pull raw records from a provider for a dataset.

Collectors are thin and side-effect free — validation, normalization, persistence
and quality scoring happen in ``pipelines`` (see ``docs/DATA_ARCHITECTURE.md`` §2).
"""

from __future__ import annotations

from datetime import date, datetime

from src.data.providers.base import DataProvider
from src.data.records import EODBar, IndexBar, NewsItem


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


__all__ = ["collect_eod", "collect_index", "collect_news"]
