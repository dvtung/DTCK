"""Unit tests for SSI FastConnect provider (src/data/providers/ssi.py).

Verifies authentication flow (Market/AccessToken with caching and 401 refresh),
stock EOD data mapping (Market/DailyOhlc), index data mapping (Market/DailyIndex),
pagination, and registry integration.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import httpx
import pytest

from src.data.providers import create_provider
from src.data.providers.ssi import SSIFastConnectProvider
from src.data.records import EODBar, IndexBar


def test_missing_credentials_raises_value_error() -> None:
    provider = SSIFastConnectProvider(
        consumer_id="",
        consumer_secret="",
        access_token="",
        api_url="https://fc-data.ssi.com.vn",
    )
    with pytest.raises(ValueError, match="missing SSI_CONSUMER_ID"):
        provider.get_access_token()


def test_access_token_generation_and_caching() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/api/v2/Market/AccessToken":
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["consumerID"] == "test_id"
            assert payload["consumerSecret"] == "test_secret"
            return httpx.Response(
                200,
                json={
                    "message": "Success",
                    "status": 200,
                    "data": {"accessToken": "jwt_token_12345"},
                },
            )
        return httpx.Response(404)

    provider = SSIFastConnectProvider(
        consumer_id="test_id",
        consumer_secret="test_secret",
        transport=httpx.MockTransport(handler),
    )

    token1 = provider.get_access_token()
    assert token1 == "jwt_token_12345"
    assert len(calls) == 1

    # Second call uses cache
    token2 = provider.get_access_token()
    assert token2 == "jwt_token_12345"
    assert len(calls) == 1
def test_fetch_eod_parses_rows_and_pagination() -> None:
    requests_made = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests_made.append(request)
        if request.url.path == "/api/v2/Market/AccessToken":
            return httpx.Response(
                200,
                json={"status": 200, "data": {"accessToken": "valid_token"}},
            )
        if request.url.path == "/api/v2/Market/DailyOhlc":
            assert request.headers["Authorization"] == "Bearer valid_token"
            page_index = request.url.params.get("pageIndex")
            symbol = request.url.params.get("symbol")
            assert symbol == "SSI"
            assert request.url.params.get("fromDate") == "10/08/2023"
            assert request.url.params.get("toDate") == "12/08/2023"

            if page_index == "1":
                return httpx.Response(
                    200,
                    json={
                        "message": "Success",
                        "status": "Success",
                        "totalRecord": 2,
                        "data": [
                            {
                                "Symbol": "SSI",
                                "Market": "HOSE",
                                "TradingDate": "10/08/2023",
                                "Open": "28600",
                                "High": "28850",
                                "Low": "28100",
                                "Close": "28100",
                                "Volume": "23382100",
                                "Value": "663258204999",
                            },
                            {
                                "Symbol": "SSI",
                                "Market": "HOSE",
                                "TradingDate": "11/08/2023",
                                "Open": "28250",
                                "High": "28300",
                                "Low": "27650",
                                "Close": "28150",
                                "Volume": "27536000",
                                "Value": "769411290000",
                            },
                        ],
                    },
                )
            return httpx.Response(
                200,
                json={"message": "Success", "status": "Success", "totalRecord": 2, "data": []},
            )
        return httpx.Response(404)

    provider = SSIFastConnectProvider(
        consumer_id="id1",
        consumer_secret="sec1",
        transport=httpx.MockTransport(handler),
    )

    bars = provider.fetch_eod(["SSI"], date(2023, 8, 10), date(2023, 8, 12))
    assert len(bars) == 2
    assert isinstance(bars[0], EODBar)
    assert bars[0].symbol == "SSI"
    assert bars[0].exchange == "HOSE"
    assert bars[0].trade_date == date(2023, 8, 10)
    assert bars[0].open == Decimal("28600")
    assert bars[0].high == Decimal("28850")
    assert bars[0].low == Decimal("28100")
    assert bars[0].close == Decimal("28100")
    assert bars[0].volume == 23382100
    assert bars[0].trading_value == Decimal("663258204999")

    assert bars[1].trade_date == date(2023, 8, 11)
    assert bars[1].close == Decimal("28150")


def test_fetch_index_parses_rows() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/Market/DailyIndex":
            assert request.url.params.get("indexId") == "VNINDEX"
            return httpx.Response(
                200,
                json={
                    "message": "Success",
                    "status": "Success",
                    "totalRecord": 1,
                    "data": [
                        {
                            "IndexId": "VNINDEX",
                            "IndexValue": "1250.5",
                            "TradingDate": "14/08/2023",
                            "TotalMatchVol": "500000000",
                            "TotalMatchVal": "12000000000000",
                        }
                    ],
                },
            )
        return httpx.Response(404)

    provider = SSIFastConnectProvider(
        access_token="direct_mock_token",
        transport=httpx.MockTransport(handler),
    )

    bars = provider.fetch_index(["VNINDEX"], date(2023, 8, 14), date(2023, 8, 14))
    assert len(bars) == 1
    assert isinstance(bars[0], IndexBar)
    assert bars[0].index_code == "VNINDEX"
    assert bars[0].trade_date == date(2023, 8, 14)
    assert bars[0].close == Decimal("1250.5")
    assert bars[0].volume == 500000000
    assert bars[0].trading_value == Decimal("12000000000000")


def test_token_refresh_on_401() -> None:
    call_count = {"daily_ohlc": 0, "token": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/Market/AccessToken":
            call_count["token"] += 1
            return httpx.Response(
                200,
                json={"status": 200, "data": {"accessToken": f"token_{call_count['token']}"}},
            )
        if request.url.path == "/api/v2/Market/DailyOhlc":
            call_count["daily_ohlc"] += 1
            if call_count["daily_ohlc"] == 1:
                return httpx.Response(401, json={"message": "Unauthorized"})
            assert request.headers["Authorization"] == "Bearer token_2"
            return httpx.Response(
                200,
                json={
                    "status": 200,
                    "totalRecord": 1,
                    "data": [
                        {
                            "Symbol": "FPT",
                            "TradingDate": "01/09/2026",
                            "Open": "100000",
                            "High": "102000",
                            "Low": "99000",
                            "Close": "101000",
                            "Volume": "1000000",
                            "Value": "101000000000",
                        }
                    ],
                },
            )
        return httpx.Response(404)

    provider = SSIFastConnectProvider(
        consumer_id="cid",
        consumer_secret="csec",
        retry_backoff=0.01,
        transport=httpx.MockTransport(handler),
    )

    bars = provider.fetch_eod(["FPT"], date(2026, 9, 1), date(2026, 9, 1))
    assert len(bars) == 1
    assert bars[0].symbol == "FPT"
    assert call_count["token"] == 2
    assert call_count["daily_ohlc"] == 2


def test_registry_creates_ssi_fastconnect_provider() -> None:
    provider = create_provider("ssix_finipro")
    assert isinstance(provider, SSIFastConnectProvider)
    assert provider.supports("prices")
    assert provider.supports("index_prices")

