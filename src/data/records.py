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


@dataclass(frozen=True, slots=True)
class FinancialRow:
    """One raw financial-statement line item (§5.1).

    ``published_at`` is when the filing became public and is the look-ahead
    guard: ``None`` means the vendor did not disclose it — the value is stored
    as NULL, never guessed (spec §31 honesty rule).
    """

    symbol: str
    period_type: str  # QUARTER | YEAR
    fiscal_year: int
    fiscal_period: int  # 1-4 for quarters, 0 for a full year
    statement_type: str  # INCOME | BALANCE | CASHFLOW
    line_item: str
    value: Decimal
    report_date: date
    published_at: datetime | None = None
    currency: str = "VND"


@dataclass(frozen=True, slots=True)
class EventRow:
    """One raw corporate action/event (§7.1)."""

    symbol: str
    event_type: str  # DIVIDEND | SPLIT | EARNINGS | AGM | M&A | ...
    event_date: date
    announced_date: date | None = None
    details: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class MacroPoint:
    """One raw macro series observation (§8.1)."""

    indicator_code: str  # CPI, GDP, FX_USDVND, ...
    period_date: date
    value: Decimal
    unit: str


Dataset = str  # "prices" | "index_prices" | "news" | "financials" | "events" | "macro"
