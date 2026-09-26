"""Unit tests for the Yahoo chart EOD provider (public Vietnam prices).

The JSON fixture is a **recorded capture** of Yahoo's v8 chart endpoint for
FPT.VN (``tests/fixtures/yahoo_chart_sample.json``, 2026-09-01→09-25 window)
including the 11:10 split event of 2026-09-21, so a payload-shape change breaks
these tests instead of silently producing wrong prices. Network access is
opt-in through ``DTCK_LIVE_TESTS=1`` (marker: ``live``).
"""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest

from src.data.providers import create_provider, fallback_chain, get_spec
from src.data.providers.yahoo_chart import YahooChartProvider, _split_ratios
from src.data.validators import validate_eod

SAMPLE = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "yahoo_chart_sample.json").read_text(
        encoding="utf-8"
    )
)
LIVE = os.getenv("DTCK_LIVE_TESTS") == "1"
ICT = timezone(timedelta(hours=7))
START = date(2026, 9, 1)
END = date(2026, 9, 25)


def _provider(handler: Any, *, max_retries: int = 0) -> YahooChartProvider:
    spec = get_spec("yahoo")
    return YahooChartProvider(
        provider_id="yahoo",
        eod_config=dict(spec.endpoints["eod"]),
        timeout=5.0,
        max_retries=max_retries,
        retry_backoff=0.0,
        transport=httpx.MockTransport(handler),
    )


def _ok(_: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=SAMPLE)


def _bars() -> list[Any]:
    return _provider(_ok).fetch_eod(["FPT"], START, END)


# --------------------------------------------------------------------- parsing
def test_parses_recorded_sample_into_bars() -> None:
    bars = _bars()
    # 19 timestamped rows minus the 5 zero-volume placeholders (Sep 1, 2, 9, 21, 22).
    assert len(bars) == 14
    assert all(bar.symbol == "FPT" for bar in bars)
    assert all(bar.exchange == "HOSE" for bar in bars)
    assert [bar.trade_date for bar in bars] == sorted(bar.trade_date for bar in bars)
    assert bars[0].trade_date == date(2026, 9, 3)
    assert bars[-1].trade_date == END


def test_zero_volume_and_null_rows_are_dropped_not_fabricated() -> None:
    dates = {bar.trade_date for bar in _bars()}
    for gap in (date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 9)):
        assert gap not in dates  # zero-volume placeholders never become bars
    payload = {
        "chart": {
            "result": [
                {
                    "meta": {"symbol": "FPT.VN"},
                    "timestamp": [1788228000, 1788314400],
                    "indicators": {
                        "quote": [
                            {
                                "open": [None, 100.0],
                                "high": [None, 110.0],
                                "low": [None, 90.0],
                                "close": [None, 105.0],
                                "volume": [None, 0],
                            }
                        ]
                    },
                }
            ],
            "error": None,
        }
    }
    assert _provider(lambda _: httpx.Response(200, json=payload))._map_rows(payload) == []


def test_split_unadjustment_restores_raw_prints() -> None:
    bars = {bar.trade_date: bar for bar in _bars()}
    # Pre-split (11:10 on 2026-09-21): Yahoo serves 65636.3671875 — the raw
    # close was 72200; the 4508020 traded shares appear scaled by ×1.1.
    pre = bars[date(2026, 9, 3)]
    assert pre.close == Decimal("72200")
    assert pre.open == Decimal("73000")
    assert pre.volume == 4098200
    # Post-split rows are untouched (whole VND as traded).
    post = bars[END]
    assert post.close == Decimal("64700.0")
    assert post.volume == 5247708


def test_trading_value_is_close_times_volume() -> None:
    for bar in _bars():
        assert bar.trading_value == (bar.close * bar.volume).quantize(Decimal("0.01"))


def test_bars_pass_the_quality_validator() -> None:
    assert validate_eod(_bars(), start=START, end=END) == []


def test_split_ratios_sorted_and_zero_denominator_rejected() -> None:
    payload = {
        "events": {
            "splits": {
                "2": {"date": 2, "numerator": 2.0, "denominator": 1.0},
                "1": {"date": 1, "numerator": 11.0, "denominator": 10.0},
            }
        }
    }
    assert _split_ratios(payload) == [(1, Decimal("1.1")), (2, Decimal("2"))]
    bad = {"events": {"splits": {"x": {"date": 1, "numerator": 1, "denominator": 0}}}}
    with pytest.raises(ValueError, match="zero denominator"):
        _split_ratios(bad)


# -------------------------------------------------------------------- requests
def test_request_targets_vn_ticker_with_epoch_window_and_descriptive_ua() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=SAMPLE)

    _provider(handler).fetch_eod(["fpt"], START, END)
    assert len(seen) == 1
    request = seen[0]
    assert request.url.path == "/v8/finance/chart/FPT.VN"
    params = request.url.params
    assert params["interval"] == "1d"
    assert params["events"] == "split"
    # period1 = START 00:00 ICT; period2 ≥ today+1d so post-window splits show.
    assert int(params["period1"]) == int(datetime(2026, 9, 1, tzinfo=ICT).timestamp())
    today = datetime.now(tz=UTC).astimezone(ICT).date()
    assert int(params["period2"]) >= int(
        datetime(today.year, today.month, today.day, tzinfo=ICT).timestamp()
    )
    # Descriptive UA — Yahoo 429s the default python-httpx agent.
    assert request.headers["User-Agent"].startswith("DTCK/")


def test_already_suffixed_symbol_is_not_double_suffixed() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=SAMPLE)

    _provider(handler).fetch_eod(["FPT.VN"], START, END)
    assert seen[0].url.path.endswith("/FPT.VN")


# ----------------------------------------------------------------------- errors
def test_error_payload_raises_with_vendor_message() -> None:
    payload = {
        "chart": {
            "result": None,
            "error": {"code": "Not Found", "description": "No data found, symbol may be delisted"},
        }
    }
    provider = _provider(lambda _: httpx.Response(200, json=payload))
    with pytest.raises(ValueError, match="No data found"):
        provider.fetch_eod(["FPT"], START, END)


def test_malformed_payloads_raise_clearly() -> None:
    provider = _provider(lambda _: httpx.Response(200, json={}))
    with pytest.raises(ValueError, match="missing 'chart'"):
        provider.fetch_eod(["FPT"], START, END)
    no_symbol = {"chart": {"result": [{"meta": {}, "timestamp": []}], "error": None}}
    with pytest.raises(ValueError, match="no symbol in meta"):
        _provider(lambda _: httpx.Response(200, json=no_symbol))._map_rows(no_symbol)


def test_http_failures_raise_connection_error_after_retries() -> None:
    provider = _provider(lambda _: httpx.Response(503), max_retries=1)
    with pytest.raises(ConnectionError, match="failed after 2 attempts"):
        provider.fetch_eod(["FPT"], START, END)


# --------------------------------------------------------------------- registry
def test_registry_builds_yahoo_provider_and_lists_it_first_in_fallback() -> None:
    provider = create_provider("yahoo", transport=httpx.MockTransport(_ok))
    assert isinstance(provider, YahooChartProvider)
    assert provider.supports("prices")
    assert not provider.supports("news")
    assert get_spec("yahoo").endpoints_status.startswith("VERIFIED_")
    assert fallback_chain("market")[0] == "yahoo"


@pytest.mark.live
@pytest.mark.skipif(not LIVE, reason="set DTCK_LIVE_TESTS=1 to hit the network")
def test_live_yahoo_chart_returns_validated_bars() -> None:
    provider = create_provider("yahoo")
    today = datetime.now(tz=UTC).astimezone(ICT).date()
    bars = provider.fetch_eod(["FPT"], today.replace(day=1), today)
    assert bars, "live Yahoo chart returned no bars"
    issues = validate_eod(bars, start=bars[0].trade_date, end=bars[-1].trade_date)
    assert issues == [], issues
    print(f"live yahoo: {len(bars)} bars, latest={bars[-1].trade_date}")

