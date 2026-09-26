"""Raw record types exchanged between collectors, validators and normalizers.

These are provider-agnostic: a provider converts its own payload into these
records, validators/normalizers/quality never see vendor-specific shapes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class EODBar:
    """One raw end-of-day OHLCV row for a single symbol (§4.1 DATABASE_SCHEMA)."""

    symbol: str
    exchange: str
    trade_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    trading_value: Decimal


@dataclass(frozen=True, slots=True)
class IndexBar:
    """One raw index OHLCV row (VNINDEX, VN30, …) (§4.3)."""

    index_code: str
    trade_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    trading_value: Decimal


@dataclass(frozen=True, slots=True)
class NewsItem:
    """One raw news item (§7.2) with optional symbol links (§7.3)."""

    source: str
    title: str
    content: str
    published_at: datetime
    symbols: tuple[str, ...] = ()
    event_type: str | None = None
    sentiment: Decimal | None = None
    importance: Decimal | None = None


Dataset = str  # "prices" | "index_prices" | "news"
