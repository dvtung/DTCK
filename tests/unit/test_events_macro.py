"""Unit tests for Yahoo corporate actions + IMF macro providers (GĐ 2)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import httpx
import pytest

from src.data.providers.imf_macro import ImfMacroProvider
from src.data.providers.yahoo_chart import YahooChartProvider

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


def _yahoo_cfg() -> dict[str, object]:
    return {
        "url": CHART_URL,
        "symbol_suffix": ".VN",
        "interval": "1mo",
        "timezone_offset_hours": 7,
        "user_agent": "DTCK/test",
        "exchange": "HOSE",
    }


def _chart_payload(events: dict[str, object]) -> dict[str, object]:
    return {"chart": {"result": [{"events": events, "timestamp": [], "indicators": {}}]}}


def _yahoo(handler) -> YahooChartProvider:
    return YahooChartProvider(
        provider_id="yahoo",
        eod_config=_yahoo_cfg(),
        timeout=5.0,
        max_retries=0,
        retry_backoff=0.0,
        transport=httpx.MockTransport(handler),
    )


class TestYahooEvents:
    def test_supports_events_alongside_prices(self) -> None:
        provider = _yahoo(lambda r: httpx.Response(200, json=_chart_payload({})))
        assert provider.supports("events")
        assert provider.supports("prices")

    def test_maps_dividends_and_splits(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.params.get("events") == "div,split"
            assert "FPT.VN" in str(request.url)
            return httpx.Response(
                200,
                json=_chart_payload(
                    {
                        "dividends": {"1": {"amount": 597.742, "date": 1655078400}},
                        "splits": {
                            "1": {
                                "date": 1655078400,
                                "numerator": 6.0,
                                "denominator": 5.0,
                                "splitRatio": "6:5",
                            }
                        },
                    }
                ),
            )

        rows = _yahoo(handler).fetch_events(["FPT"], since=date(2020, 1, 1))
        assert {r.event_type for r in rows} == {"DIVIDEND", "SPLIT"}

        dividend = next(r for r in rows if r.event_type == "DIVIDEND")
        assert dividend.symbol == "FPT"
        assert dividend.announced_date is None  # Yahoo publishes none — no guessing
        assert dividend.details is not None
        assert float(dividend.details["cash_amount"]) == pytest.approx(597.742)

        split = next(r for r in rows if r.event_type == "SPLIT")
        assert split.details is not None
        assert split.details["numerator"] == 6
        assert split.details["denominator"] == 5
        assert split.details["ratio"] == "6:5"

    def test_events_before_since_are_filtered(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, json=_chart_payload({"dividends": {"1": {"amount": 1.0, "date": 946684800}}})
            )

        rows = _yahoo(handler).fetch_events(["FPT"], since=date(2020, 1, 1))
        assert rows == []

    def test_empty_result_is_not_an_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"chart": {"result": [], "error": None}})

        assert _yahoo(handler).fetch_events(["FPT"], since=date(2020, 1, 1)) == []


class TestImfMacro:
    def _imf(self, payloads: dict[str, dict[str, object]]) -> ImfMacroProvider:
        def handler(request: httpx.Request) -> httpx.Response:
            code = request.url.path.rstrip("/").split("/")[-2]
            return httpx.Response(200, json=payloads[code])

        return ImfMacroProvider(
            country="VNM",
            max_year_offset=1,
            transport=httpx.MockTransport(handler),
            timeout_s=5.0,
        )

    def test_maps_annual_series(self) -> None:
        payload = {"values": {"NGDP_RPCH": {"VNM": {"2023": 5.1, "2024": 7.0}}}}
        rows = self._imf({"NGDP_RPCH": payload}).fetch_macro(
            ["GDP_GROWTH_PCT"], start=date(2010, 1, 1), end=date(2026, 12, 31)
        )
        assert len(rows) == 2
        assert {r.indicator_code for r in rows} == {"GDP_GROWTH_PCT"}
        assert all(r.unit == "percent" for r in rows)
        latest = max(rows, key=lambda r: r.period_date)
        assert latest.period_date == date(2024, 12, 31)
        assert latest.value == Decimal("7.0")

    def test_projections_are_never_stored(self) -> None:
        """Future WEO years are forecasts — persist only completed years (§31)."""
        from datetime import datetime as _dt

        current = _dt.now().date().year
        payload = {
            "values": {
                "NGDP_RPCH": {
                    "VNM": {"2024": 7.0, str(current): 7.9, str(current + 5): 6.0}
                }
            }
        }
        rows = self._imf({"NGDP_RPCH": payload}).fetch_macro(
            ["GDP_GROWTH_PCT"], start=date(2000, 1, 1), end=date(2100, 1, 1)
        )
        years = {r.period_date.year for r in rows}
        assert current not in years
        assert (current + 5) not in years

    def test_window_is_respected(self) -> None:
        payload = {"values": {"PCPIPCH": {"VNM": {"2010": 9.0, "2020": 3.2}}}}
        rows = self._imf({"PCPIPCH": payload}).fetch_macro(
            ["CPI_INFLATION_PCT"], start=date(2015, 1, 1), end=date(2021, 12, 31)
        )
        assert [r.period_date.year for r in rows] == [2020]

    def test_unknown_indicator_is_rejected(self) -> None:
        provider = self._imf({})
        with pytest.raises(KeyError):
            provider.fetch_macro(["NOPE"], start=date(2000, 1, 1), end=date(2100, 1, 1))

    def test_registry_uses_configured_indicators(self) -> None:
        from src.data.providers.registry import create_provider

        provider = create_provider("imf_worldbank")
        assert isinstance(provider, ImfMacroProvider)
        assert provider.supports("macro")
        assert "GDP_GROWTH_PCT" in provider._indicators
