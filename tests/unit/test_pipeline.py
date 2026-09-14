"""Unit tests for T004 — data ingestion pipeline components.

Covers: FixtureProvider (determinism, filtering), collectors, validators,
normalizers — all without a database.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from src.data.collectors import collect_eod, collect_index, collect_news
from src.data.normalizers import normalize_eod, normalize_index, normalize_news
from src.data.providers.fixture import build_fixture_provider, seed_value
from src.data.records import EODBar, IndexBar, NewsItem
from src.data.validators import ValidationIssue, validate_eod, validate_index, validate_news

NOW = datetime.now(tz=UTC)
START = date(2026, 9, 1)
END = date(2026, 9, 5)


def make_eod(symbol="FPT", d=None, **over):
    d = d or date(2026, 9, 1)
    defaults = dict(
        symbol=symbol,
        exchange="HOSE",
        trade_date=d,
        open=Decimal("50000"),
        high=Decimal("51000"),
        low=Decimal("49000"),
        close=Decimal("50500"),
        volume=500_000,
        trading_value=Decimal("25_000_000_000"),
    )
    defaults.update(over)
    return EODBar(**defaults)


def make_index(code="VNINDEX", d=None, **over):
    d = d or date(2026, 9, 1)
    defaults = dict(
        index_code=code,
        trade_date=d,
        open=Decimal("1200"),
        high=Decimal("1210"),
        low=Decimal("1190"),
        close=Decimal("1205"),
        volume=5_000_000,
        trading_value=Decimal("6_000_000_000"),
    )
    defaults.update(over)
    return IndexBar(**defaults)


def make_news(**over):
    defaults = dict(
        source="test",
        title="Test headline",
        content="Test content",
        published_at=datetime(2026, 9, 1, tzinfo=UTC),
        symbols=("FPT", "VCB"),
        event_type=None,
        sentiment=Decimal("0.1"),
        importance=Decimal("0.5"),
    )
    defaults.update(over)
    return NewsItem(**defaults)


# --------------------------------------------------------------------------- #
#  FixtureProvider tests
# --------------------------------------------------------------------------- #


class TestFixtureProvider:
    def test_deterministic_same_inputs_same_outputs(self):
        p1 = build_fixture_provider(symbols=["FPT"], start=START, end=END)
        p2 = build_fixture_provider(symbols=["FPT"], start=START, end=END)
        assert p1.fetch_eod(["fpt"], START, END) == p2.fetch_eod(["fpt"], START, END)

    def test_different_inputs_different_outputs(self):
        p1 = build_fixture_provider(symbols=["FPT"], start=START, end=END)
        p2 = build_fixture_provider(symbols=["VCB"], start=START, end=END)
        bars1 = p1.fetch_eod(["fpt"], START, END)
        bars2 = p2.fetch_eod(["vcb"], START, END)
        assert bars1 != bars2

    def test_filters_by_symbol(self):
        p = build_fixture_provider(symbols=["FPT", "VCB"], start=START, end=END)
        fpt_only = p.fetch_eod(["FPT"], START, END)
        assert {b.symbol for b in fpt_only} == {"FPT"}

    def test_filters_by_date_range(self):
        p = build_fixture_provider(symbols=["FPT"], start=START, end=END)
        all_bars = p.fetch_eod(["FPT"], START, END)
        assert len(all_bars) == 4  # Sep 1-4 (Sep 5 is Saturday)
        assert all(START <= b.trade_date <= END for b in all_bars)

    def test_weekdays_only(self):
        p = build_fixture_provider(symbols=["FPT"], start=date(2026, 9, 1), end=date(2026, 9, 10))
        bars = p.fetch_eod(["FPT"], date(2026, 9, 1), date(2026, 9, 10))
        assert len(bars) == 8  # Mon-Fri: 1,2,3,4,7,8,9,10
        assert all(b.trade_date.weekday() < 5 for b in bars)

    def test_no_weekend_data(self):
        p = build_fixture_provider(symbols=["FPT"], start=date(2026, 9, 4), end=date(2026, 9, 6))
        bars = p.fetch_eod(["FPT"], date(2026, 9, 4), date(2026, 9, 6))
        dates = {b.trade_date for b in bars}
        assert date(2026, 9, 5) not in dates  # Saturday
        assert date(2026, 9, 6) not in dates  # Sunday

    def test_fetch_empty_symbols(self):
        p = build_fixture_provider(symbols=["FPT"], start=START, end=END)
        assert p.fetch_eod([], START, END) == []

    def test_fetch_news(self):
        p = build_fixture_provider(symbols=["FPT"], start=START, end=END)
        since = datetime(2026, 8, 31, tzinfo=UTC)
        news = p.fetch_news(since)
        assert len(news) == 1
        assert news[0].source == "fixture"
        assert "FPT" in news[0].symbols

    def test_fetch_news_filters_by_since(self):
        p = build_fixture_provider(symbols=["FPT"], start=START, end=END)
        future = datetime(2027, 1, 1, tzinfo=UTC)
        assert p.fetch_news(future) == []

    def test_seed_value_is_stable(self):
        assert seed_value(["FPT"], START, END) == seed_value(["fpt"], START, END)
        assert seed_value(["FPT"], START, END) != seed_value(["VCB"], START, END)


# --------------------------------------------------------------------------- #
#  Collector tests
# --------------------------------------------------------------------------- #


class TestCollectors:
    def test_collect_eod_filters_by_symbol(self):
        provider = build_fixture_provider(symbols=["FPT", "VCB"], start=START, end=END)
        bars = collect_eod(provider, ["FPT"], START, END)
        assert {b.symbol for b in bars} == {"FPT"}

    def test_collect_eod_uppercase_symbols(self):
        provider = build_fixture_provider(symbols=["fpt"], start=START, end=END)
        bars = collect_eod(provider, ["FPT"], START, END)
        assert len(bars) > 0
        assert all(b.symbol == "FPT" for b in bars)

    def test_collect_eod_dedup_symbols(self):
        provider = build_fixture_provider(symbols=["FPT"], start=START, end=END)
        bars = collect_eod(provider, ["FPT", "fpt", "FPT"], START, END)
        assert {b.symbol for b in bars} == {"FPT"}

    def test_collect_index(self):
        provider = build_fixture_provider(
            symbols=["FPT"], start=START, end=END, indexes=["VNINDEX"]
        )
        bars = collect_index(provider, ["VNINDEX"], START, END)
        assert len(bars) == 4
        assert all(b.index_code == "VNINDEX" for b in bars)

    def test_collect_news(self):
        provider = build_fixture_provider(symbols=["FPT"], start=START, end=END)
        since = datetime(2026, 8, 31, tzinfo=UTC)
        items = collect_news(provider, since)
        assert len(items) == 1

    def test_collect_raises_for_unsupported_dataset(self):
        provider = build_fixture_provider(symbols=["FPT"], start=START, end=END)
        provider.SUPPORTED_DATASETS = frozenset({"prices"})
        collect_eod(provider, ["FPT"], START, END)  # ok
        with pytest.raises(ValueError, match="does not support"):
            collect_news(provider, NOW)


# --------------------------------------------------------------------------- #
#  Validator tests
# --------------------------------------------------------------------------- #


class TestValidators:
    def test_validate_eod_clean(self):
        bars = [make_eod(), make_eod(d=date(2026, 9, 2))]
        assert validate_eod(bars, start=START, end=END) == []

    def test_validate_eod_duplicate(self):
        d = make_eod()
        issues = validate_eod([d, d], start=START, end=END)
        assert any("duplicate" in i.message for i in issues)

    def test_validate_eod_out_of_window(self):
        bar = make_eod(d=date(2026, 8, 1))
        issues = validate_eod([bar], start=START, end=END)
        assert any("outside requested window" in i.message for i in issues)

    def test_validate_eod_high_less_than_low(self):
        bar = make_eod(high=Decimal("49000"), low=Decimal("50000"))
        issues = validate_eod([bar], start=START, end=END)
        assert any("high < low" in i.message for i in issues)

    def test_validate_eod_close_above_high(self):
        bar = make_eod(high=Decimal("50000"), close=Decimal("51000"))
        issues = validate_eod([bar], start=START, end=END)
        assert any("close > high" in i.message for i in issues)

    def test_validate_eod_close_below_low(self):
        bar = make_eod(low=Decimal("50000"), close=Decimal("49000"))
        issues = validate_eod([bar], start=START, end=END)
        assert any("close < low" in i.message for i in issues)

    def test_validate_eod_negative_price(self):
        bar = make_eod(open=Decimal("-1"))
        issues = validate_eod([bar], start=START, end=END)
        assert any("must be > 0" in i.message and "open" in i.field for i in issues)

    def test_validate_eod_negative_volume(self):
        bar = make_eod(volume=-100)
        issues = validate_eod([bar], start=START, end=END)
        assert any("volume" in i.field and "must be >= 0" in i.message for i in issues)

    def test_validate_index_same_checks(self):
        bar = make_index()
        assert validate_index([bar], start=START, end=END) == []
        bad = make_index(low=Decimal("1210"), high=Decimal("1190"))
        issues = validate_index([bad], start=START, end=END)
        assert any("high < low" in i.message for i in issues)

    def test_validate_news_clean(self):
        assert validate_news([make_news()]) == []

    def test_validate_news_empty_title(self):
        issues = validate_news([make_news(title="  ")])
        assert any("title" in i.field and "empty" in i.message for i in issues)

    def test_validate_news_empty_content(self):
        issues = validate_news([make_news(content="")])
        assert any("content" in i.field and "empty" in i.message for i in issues)

    def test_validate_news_future_publication(self):
        items = [make_news(published_at=datetime(2030, 1, 1, tzinfo=UTC))]
        issues = validate_news(items)
        assert any("future" in i.message for i in issues)

    def test_validate_news_sentiment_out_of_range(self):
        issues = validate_news([make_news(sentiment=Decimal("2"))])
        assert any("sentiment" in i.field for i in issues)

    def test_validate_news_importance_out_of_range(self):
        issues = validate_news([make_news(importance=Decimal("5"))])
        assert any("importance" in i.field for i in issues)

    def test_validate_news_duplicate(self):
        item = make_news()
        issues = validate_news([item, item])
        assert any("duplicate" in i.message for i in issues)

    def test_validation_issue_str(self):
        issue = ValidationIssue("prices", "FPT@2026-09-01", "open", "must be > 0")
        assert "FPT@2026-09-01" in str(issue)
        assert "must be > 0" in str(issue)


# --------------------------------------------------------------------------- #
#  Normalizer tests
# --------------------------------------------------------------------------- #


class TestNormalizers:
    def test_normalize_eod_valid(self):
        bars = [make_eod()]
        stock_ids = {"FPT": 1}
        rows, issues = normalize_eod(bars, stock_ids, source="test", ingested_at=NOW)
        assert len(rows) == 1
        assert rows[0]["stock_id"] == 1
        assert rows[0]["source"] == "test"
        assert issues == []

    def test_normalize_eod_unknown_symbol(self):
        bars = [make_eod(symbol="UNKNOWN")]
        stock_ids = {"FPT": 1}
        rows, issues = normalize_eod(bars, stock_ids, source="test", ingested_at=NOW)
        assert len(rows) == 0
        assert len(issues) == 1
        assert "not in reference universe" in issues[0].message

    def test_normalize_index(self):
        bars = [make_index()]
        rows = normalize_index(bars, source="test", ingested_at=NOW)
        assert len(rows) == 1
        assert rows[0]["index_code"] == "VNINDEX"

    def test_normalize_news_valid(self):
        items = [make_news(symbols=("FPT", "VCB"))]
        stock_ids = {"FPT": 1, "VCB": 2}
        news_rows, links, issues = normalize_news(items, stock_ids, ingested_at=NOW)
        assert len(news_rows) == 1
        assert links[0] == [1, 2]
        assert issues == []

    def test_normalize_news_unknown_symbol(self):
        items = [make_news(symbols=("FPT", "UNKNOWN"))]
        stock_ids = {"FPT": 1}
        news_rows, links, issues = normalize_news(items, stock_ids, ingested_at=NOW)
        assert len(news_rows) == 1
        assert links[0] == [1]
        assert len(issues) == 1
        assert "UNKNOWN" in issues[0].message
