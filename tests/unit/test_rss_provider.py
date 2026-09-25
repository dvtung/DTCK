"""RSS news provider (W2): parsing, symbol linking, fetching.

The XML fixture is a **recorded capture** of CaféF's market feed
(``tests/fixtures/cafef_rss_sample.xml``) so a schema change breaks these tests
instead of silently producing empty news. Network access is opt-in through
``DTCK_LIVE_TESTS=1`` (marker: ``live``).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from src.data.providers.rss import (
    RssNewsProvider,
    match_symbols,
    parse_feed,
    parse_pub_date,
    strip_html,
)

SAMPLE = (Path(__file__).resolve().parents[1] / "fixtures" / "cafef_rss_sample.xml").read_text(
    encoding="utf-8"
)
UNIVERSE = frozenset({"PNJ", "FPT", "HPG", "VNM"})
LIVE = os.getenv("DTCK_LIVE_TESTS") == "1"


# ------------------------------------------------------------------- helpers
def test_strip_html_removes_tags_and_normalizes_space() -> None:
    raw = '<a href="x"><img src="y"></a>  Tin   <b>nóng</b>\n&amp; tiền tệ'
    assert strip_html(raw) == "Tin nóng & tiền tệ"


def test_parse_pub_date_rfc822_is_utc_aware() -> None:
    parsed = parse_pub_date("Fri, 25 Sep 26 19:10:00 +0700")
    assert parsed == datetime(2026, 9, 25, 12, 10, tzinfo=UTC)
    assert parsed is not None and parsed.tzinfo == UTC


def test_parse_pub_date_iso_fallback_and_garbage() -> None:
    assert parse_pub_date("2026-09-25T12:10:00Z") == datetime(2026, 9, 25, 12, 10, tzinfo=UTC)
    assert parse_pub_date("not a date") is None
    assert parse_pub_date("") is None


# ------------------------------------------------------------- symbol linking
def test_match_symbols_finds_real_tickers_only() -> None:
    text = "PNJ trình kế hoạch lỗ kỷ lục, FPT và hpg tăng nhẹ; GDP, VN, FED không phải mã"
    # Uppercase, boundary-delimited matches against the universe only:
    # "hpg" (lowercase) is not a press ticker reference and "VN"/"GDP"/"FED"
    # are not in the reference universe at all.
    assert match_symbols(text, UNIVERSE) == ["FPT", "PNJ"]


def test_match_symbols_requires_word_boundaries() -> None:
    assert match_symbols("PNJX và XFPT", UNIVERSE) == []
    assert match_symbols("(PNJ)", UNIVERSE) == ["PNJ"]
    assert match_symbols("PNJ", frozenset()) == []


# ------------------------------------------------------------------ parsing
def test_parse_feed_reads_the_recorded_sample() -> None:
    items = parse_feed(SAMPLE, source="cafef", universe=UNIVERSE)
    assert len(items) == 2
    # Oldest first → deterministic ingest order.
    assert [item.published_at for item in items] == sorted(item.published_at for item in items)
    assert all(item.source == "cafef" for item in items)
    assert all(item.published_at.tzinfo == UTC for item in items)
    # HTML was stripped from the description (CaféF embeds an <img> anchor).
    assert all("<" not in item.content for item in items)
    assert all(item.title and item.content for item in items)

    tickers = {item.title: item.symbols for item in items}
    assert any(symbols == ("PNJ",) for symbols in tickers.values()), tickers
    assert sorted(set().union(*tickers.values())) == ["PNJ"]


def test_parse_feed_skips_items_that_cannot_be_stored() -> None:
    xml = """<?xml version="1.0"?><rss><channel>
      <item><title>No date</title><description>x</description></item>
      <item><title></title><pubDate>Fri, 25 Sep 26 19:10:00 +0700</pubDate></item>
      <item><title>Good</title><description>body</description>
        <pubDate>Fri, 25 Sep 26 19:11:00 +0700</pubDate></item>
    </channel></rss>"""
    items = parse_feed(xml, source="cafef")
    assert [item.title for item in items] == ["Good"]


def test_parse_feed_handles_atom_entries_and_content_limit() -> None:
    xml = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>Atom title</title><summary>summary body</summary>
        <updated>2026-09-25T12:10:00Z</updated></entry>
    </feed>"""
    items = parse_feed(xml, source="cafef", content_limit=5)
    assert len(items) == 1
    assert items[0].content == "summa"  # limited to 5 characters
    assert items[0].published_at == datetime(2026, 9, 25, 12, 10, tzinfo=UTC)


# ----------------------------------------------------------------- fetching
def _provider(handler, **kwargs) -> RssNewsProvider:  # type: ignore[no-untyped-def]
    return RssNewsProvider(
        provider_id="cafef",
        source="cafef",
        feed_url="https://cafef.vn/feed.rss",
        timeout=5.0,
        max_retries=kwargs.pop("max_retries", 0),
        retry_backoff=0.0,
        universe=UNIVERSE,
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


def _ok(_: httpx.Request) -> httpx.Response:
    return httpx.Response(200, text=SAMPLE, headers={"Content-Type": "application/rss+xml"})


def test_fetch_news_follows_redirects_and_sends_user_agent() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if len(seen) == 1:
            return httpx.Response(302, headers={"Location": "https://cafef.vn/moved.rss"})
        return httpx.Response(200, text=SAMPLE, headers={"Content-Type": "application/rss+xml"})

    items = _provider(handler).fetch_news(datetime(2026, 1, 1, tzinfo=UTC))
    assert len(items) == 2
    assert len(seen) == 2, "the 302 must be followed"
    assert "DTCK" in seen[0].headers["User-Agent"]


def test_fetch_news_filters_by_since() -> None:
    provider = _provider(_ok)
    assert len(provider.fetch_news(datetime(2026, 1, 1, tzinfo=UTC))) == 2
    # Only the 19:10 (+0700) = 12:10 UTC item is newer than 12:00 UTC.
    assert len(provider.fetch_news(datetime(2026, 9, 25, 12, 0, tzinfo=UTC))) == 1
    assert provider.fetch_news(datetime(2030, 1, 1, tzinfo=UTC)) == []


def test_fetch_news_accepts_naive_since() -> None:
    assert len(_provider(_ok).fetch_news(datetime(2026, 1, 1))) == 2


def test_fetch_news_raises_after_retries_exhausted() -> None:
    handler = lambda _: httpx.Response(503)  # noqa: E731
    with pytest.raises(ConnectionError, match="failed after 1 attempts"):
        _provider(handler).fetch_news(datetime(2026, 1, 1, tzinfo=UTC))


def test_provider_declares_only_the_news_dataset() -> None:
    provider = _provider(_ok)
    assert provider.supports("news")
    assert not provider.supports("prices")
    with pytest.raises(NotImplementedError):
        provider.fetch_eod([], datetime(2026, 1, 1).date(), datetime(2026, 1, 2).date())


@pytest.mark.live
@pytest.mark.skipif(not LIVE, reason="set DTCK_LIVE_TESTS=1 to hit the network")
def test_live_cafef_feed_returns_items() -> None:
    from src.data.providers import create_provider

    provider = create_provider("cafef", universe=UNIVERSE)
    items = provider.fetch_news(datetime(2020, 1, 1, tzinfo=UTC))
    assert items, "live CaféF feed returned no items"
    assert all(item.title and item.published_at for item in items)
    print(f"live cafef: {len(items)} items, latest={items[-1].published_at}")
