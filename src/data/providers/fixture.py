"""Offline provider — deterministic in-memory rows for tests, demos and backfills.

Lets the whole collector → validator → normalizer → pipeline → quality chain be
exercised without any network access (KI-006: live endpoints are TO VERIFY).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from src.data.providers.base import DataProvider
from src.data.records import EODBar, IndexBar, NewsItem


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
    ) -> None:
        self.id = provider_id
        self._eod = list(eod_bars)
        self._index = list(index_bars)
        self._news = list(news_items)
        self.SUPPORTED_DATASETS = frozenset({"prices", "index_prices", "news"})

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


def build_fixture_provider(
    *,
    symbols: list[str],
    start: date,
    end: date,
    indexes: list[str] | None = None,
    provider_id: str = "fixture",
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
        provider_id=provider_id, eod_bars=eod_bars, index_bars=index_bars, news_items=news_items
    )


def seed_value(symbols: list[str], start: date, end: date) -> int:
    """Stable seed derived from the request (same request ⇒ same fixture data)."""
    payload = ",".join(sorted(s.upper() for s in symbols)) + start.isoformat() + end.isoformat()
    return sum(ord(ch) * (i + 1) for i, ch in enumerate(payload)) % 10_000


__all__ = ["FixtureProvider", "build_fixture_provider", "seed_value"]
