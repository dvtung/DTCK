"""Offline provider — deterministic in-memory rows for tests, demos and backfills.

Lets the whole collector → validator → normalizer → pipeline → quality chain be
exercised without any network access (KI-006: live endpoints are TO VERIFY).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from src.data.providers.base import DataProvider
from src.data.records import EODBar, EventRow, FinancialRow, IndexBar, NewsItem


class FixtureProvider(DataProvider):
    """Serves pre-built records regardless of the requested window."""

    id: str

    def __init__(
        self,
        *,
        provider_id: str,
        eod_bars: list[EODBar],
        index_bars: list[IndexBar],
        news_items: list[NewsItem],
        financial_rows: list[FinancialRow] | None = None,
        event_rows: list[EventRow] | None = None,
    ) -> None:
        self.id = provider_id
        self._eod = list(eod_bars)
        self._index = list(index_bars)
        self._news = list(news_items)
        self._financials = list(financial_rows or [])
        self._events = list(event_rows or [])
        datasets = {"prices", "index_prices", "news"}
        if self._financials:
            datasets.add("financials")
        if self._events:
            datasets.add("events")
        self.SUPPORTED_DATASETS = frozenset(datasets)

    def fetch_eod(self, symbols: list[str], start: date, end: date) -> list[EODBar]:
        wanted = {s.upper() for s in symbols}
        return [
            bar
            for bar in self._eod
            if bar.symbol.upper() in wanted and start <= bar.trade_date <= end
        ]

    def fetch_index(self, index_codes: list[str], start: date, end: date) -> list[IndexBar]:
        wanted = {c.upper() for c in index_codes}
        return [
            bar
            for bar in self._index
            if bar.index_code.upper() in wanted and start <= bar.trade_date <= end
        ]

    def fetch_news(self, since: datetime) -> list[NewsItem]:
        return [item for item in self._news if item.published_at > since]

    def fetch_financials(
        self, symbols: list[str], *, period_types: tuple[str, ...] = ("QUARTER", "YEAR")
    ) -> list[FinancialRow]:
        wanted = {s.upper() for s in symbols}
        types = {t.upper() for t in period_types}
        return [
            row
            for row in self._financials
            if row.symbol.upper() in wanted and row.period_type.upper() in types
        ]

    def fetch_events(self, symbols: list[str], *, since: date) -> list[EventRow]:
        wanted = {s.upper() for s in symbols}
        return [
            row
            for row in self._events
            if row.symbol.upper() in wanted and row.event_date >= since
        ]


def build_fixture_provider(
    *,
    symbols: list[str],
    start: date,
    end: date,
    indexes: list[str] | None = None,
    provider_id: str = "fixture",
    include_financials: bool = False,
    include_events: bool = False,
) -> FixtureProvider:
    """Deterministic synthetic rows for ``symbols``/``indexes`` over ``[start, end]``.

    Prices follow a seeded random walk (same inputs ⇒ same outputs) so pipeline
    and quality runs are reproducible offline. Weekdays only.
    """
    import random

    rng = random.Random(seed_value(symbols, start, end))
    eod_bars: list[EODBar] = []
    for symbol in symbols:
        price = Decimal("50000")
        cursor = start
        while cursor <= end:
            if cursor.weekday() < 5:
                drift = Decimal(str(rng.uniform(-0.02, 0.02)))
                open_ = price
                close = (price * (Decimal(1) + drift)).quantize(Decimal("0.1"))
                high = max(open_, close) * Decimal("1.01")
                low = min(open_, close) * Decimal("0.99")
                eod_bars.append(
                    EODBar(
                        symbol=symbol.upper(),
                        exchange="HOSE",
                        trade_date=cursor,
                        open=open_.quantize(Decimal("0.1")),
                        high=high.quantize(Decimal("0.1")),
                        low=low.quantize(Decimal("0.1")),
                        close=close,
                        volume=rng.randint(100_000, 1_000_000),
                        trading_value=(close * Decimal(rng.randint(100_000, 1_000_000))).quantize(
                            Decimal("0.01")
                        ),
                    )
                )
                price = close
            cursor = date.fromordinal(cursor.toordinal() + 1)

    index_bars: list[IndexBar] = []
    for code in indexes or []:
        level = Decimal("1200")
        cursor = start
        while cursor <= end:
            if cursor.weekday() < 5:
                open_ = level
                close = (level * (Decimal(1) + Decimal(str(rng.uniform(-0.01, 0.01))))).quantize(
                    Decimal("0.01")
                )
                # Bracketing must use min/max(open, close): deriving `low` from the
                # previous level alone produced bars with close < low (invalid OHLC).
                index_bars.append(
                    IndexBar(
                        index_code=code.upper(),
                        trade_date=cursor,
                        open=open_.quantize(Decimal("0.01")),
                        high=(max(open_, close) * Decimal("1.005")).quantize(Decimal("0.01")),
                        low=(min(open_, close) * Decimal("0.995")).quantize(Decimal("0.01")),
                        close=close,
                        volume=rng.randint(1_000_000, 10_000_000),
                        trading_value=(
                            close * Decimal(rng.randint(1_000_000, 10_000_000))
                        ).quantize(Decimal("0.01")),
                    )
                )
                level = close
            cursor = date.fromordinal(cursor.toordinal() + 1)

    news_items = [
        NewsItem(
            source="fixture",
            title=f"Fixture market wrap {start.isoformat()}–{end.isoformat()}",
            content="Deterministic fixture content used for offline pipeline runs.",
            # 15:00 (market close) so a same-day ``since`` boundary (00:00 of
            # the request window) still yields the item under ``published > since``.
            published_at=datetime.combine(end, datetime.min.time(), tzinfo=UTC)
            + timedelta(hours=15),
            symbols=tuple(s.upper() for s in symbols[:2]),
            event_type="MARKET_WRAP",
            sentiment=Decimal("0.10"),
            importance=Decimal("0.30"),
        )
    ]
    return FixtureProvider(
        provider_id=provider_id,
        eod_bars=eod_bars,
        index_bars=index_bars,
        news_items=news_items,
        financial_rows=build_financial_fixture_rows(symbols, end=end)
        if include_financials
        else [],
        event_rows=build_event_fixture_rows(symbols, end=end) if include_events else [],
    )


#: A minimal, sector-agnostic line-item set (one per statement type) — enough
#: for the growth/quality feature engine without pretending to be full VAS.
_FIXTURE_LINE_ITEMS: tuple[tuple[str, str], ...] = (
    ("INCOME", "revenue"),
    ("INCOME", "net_profit"),
    ("BALANCE", "total_assets"),
    ("BALANCE", "equity"),
    ("CASHFLOW", "operating_cash_flow"),
)


def build_financial_fixture_rows(
    symbols: list[str], *, end: date, quarters: int = 8
) -> list[FinancialRow]:
    """Deterministic quarterly financials for ``symbols`` (offline ETL path).

    ``published_at`` is ``quarter_end + 45 days`` — the documented *fixture*
    convention for the VN filing lag, so as-of/look-ahead tests have a real
    publication boundary. Live providers must supply the vendor's own date or
    leave it NULL; this helper is test data, never a fallback for real sources.
    """
    quarter_end_month = ((end.month - 1) // 3 + 1) * 3
    cursor_year, cursor_month = end.year, quarter_end_month
    periods: list[date] = []
    for _ in range(quarters):
        day = {3: 31, 6: 30, 9: 30, 12: 31}[cursor_month]
        periods.append(date(cursor_year, cursor_month, day))
        cursor_month -= 3
        if cursor_month <= 0:
            cursor_month += 12
            cursor_year -= 1
    periods.reverse()

    rows: list[FinancialRow] = []
    for symbol in symbols:
        base = Decimal(1_000_000_000_000)
        for index, period_end in enumerate(periods):
            growth = (Decimal("1.03") ** index).quantize(Decimal("0.0001"))
            report_date = period_end
            published = datetime(
                report_date.year, report_date.month, report_date.day, tzinfo=UTC
            ) + timedelta(days=45)
            fiscal_period = (report_date.month - 1) // 3 + 1
            for statement_type, line_item in _FIXTURE_LINE_ITEMS:
                scale = Decimal("0.1") if line_item == "net_profit" else Decimal("1")
                rows.append(
                    FinancialRow(
                        symbol=symbol.upper(),
                        period_type="QUARTER",
                        fiscal_year=report_date.year,
                        fiscal_period=fiscal_period,
                        statement_type=statement_type,
                        line_item=line_item,
                        value=(base * growth * scale).quantize(Decimal("0.01")),
                        report_date=report_date,
                        published_at=published,
                    )
                )
    return rows


def build_event_fixture_rows(symbols: list[str], *, end: date) -> list[EventRow]:
    """One deterministic dividend event per symbol (offline ETL path)."""
    event_date = end - timedelta(days=30)
    return [
        EventRow(
            symbol=symbol.upper(),
            event_type="DIVIDEND",
            event_date=event_date,
            announced_date=event_date - timedelta(days=20),
            details={"cash_dividend_vnd": 500},
        )
        for symbol in symbols
    ]


def seed_value(symbols: list[str], start: date, end: date) -> int:
    """Stable seed derived from the request (same request ⇒ same fixture data)."""
    payload = ",".join(sorted(s.upper() for s in symbols)) + start.isoformat() + end.isoformat()
    return sum(ord(ch) * (i + 1) for i, ch in enumerate(payload)) % 10_000


__all__ = [
    "FixtureProvider",
    "build_event_fixture_rows",
    "build_financial_fixture_rows",
    "build_fixture_provider",
    "seed_value",
]
