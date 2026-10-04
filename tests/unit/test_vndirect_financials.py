"""Unit tests for the GĐ 2 financials/corporate-events ETL (offline)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import httpx
import pytest

from src.data.providers.vndirect_financials import VNDirectFinancialProvider
from src.data.records import EventRow, FinancialRow
from src.data.validators import validate_events, validate_financials

BASE = "https://finfo-api.vndirect.com.vn/v4"


def _provider(handler) -> VNDirectFinancialProvider:
    return VNDirectFinancialProvider(
        base_url=BASE, transport=httpx.MockTransport(handler), timeout_s=5.0
    )


def _handler(payload: dict[str, object], *, income_only: bool = True):
    """Route the multi-statement loop: only ``modelType:1`` (INCOME) is served."""

    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params.get("q", "")
        if income_only and "modelType:1" not in query:
            return httpx.Response(200, json={"data": []})
        return httpx.Response(200, json=payload)

    return handler


def _financial_payload() -> dict[str, object]:
    return {
        "data": [
            {
                "code": "FPT",
                "fiscalDate": "2024-06-30",
                "itemCode": "revenue",
                "numericValue": 1500000000000,
                "publicDate": "2024-07-25T09:00:00",
            },
            {
                "code": "FPT",
                "fiscalDate": "2024-06-30",
                "itemCode": "net_profit",
                "numericValue": 200000000000,  # no publicDate → published_at stays None
            },
            {
                # Missing numericValue → skipped, never zero-filled.
                "code": "FPT",
                "fiscalDate": "2024-06-30",
                "itemCode": "eps",
            },
        ]
    }


class TestFinancialMapping:
    def test_maps_line_items_with_publication_date(self) -> None:
        rows = _provider(_handler(_financial_payload())).fetch_financials(
            ["FPT"], period_types=("QUARTER",)
        )
        assert len(rows) == 2  # the value-less row is skipped
        assert all(isinstance(row, FinancialRow) for row in rows)

        revenue = next(r for r in rows if r.line_item == "revenue")
        assert revenue.symbol == "FPT"
        assert revenue.period_type == "QUARTER"
        assert revenue.fiscal_year == 2024
        assert revenue.fiscal_period == 2
        assert revenue.report_date == date(2024, 6, 30)
        assert revenue.value == Decimal("1500000000000")
        assert revenue.published_at is not None
        assert revenue.published_at.date() == date(2024, 7, 25)

    def test_missing_publication_date_stays_none(self) -> None:
        rows = _provider(_handler(_financial_payload())).fetch_financials(
            ["FPT"], period_types=("QUARTER",)
        )
        profit = next(r for r in rows if r.line_item == "net_profit")
        assert profit.published_at is None  # never backfilled with a guess

    def test_year_period_type_sets_fiscal_period_zero(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "code": "FPT",
                            "fiscalDate": "2024-12-31",
                            "itemCode": "revenue",
                            "numericValue": 1,
                        }
                    ]
                },
            )

        rows = _provider(handler).fetch_financials(["FPT"], period_types=("YEAR",))
        assert rows[0].period_type == "YEAR"
        assert rows[0].fiscal_period == 0

    def test_malformed_payload_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"data": "not-a-list"})

        with pytest.raises(ValueError, match="'data' is not a list"):
            _provider(handler).fetch_financials(["FPT"], period_types=("QUARTER",))

    def test_supported_datasets(self) -> None:
        provider = _provider(lambda r: httpx.Response(200, json={"data": []}))
        assert provider.supports("financials")
        assert provider.supports("events")
        assert not provider.supports("prices")


class TestEventMapping:
    def test_maps_events(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path.endswith("/events")
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "code": "FPT",
                            "date": "2026-03-15",
                            "eventType": "dividend",
                            "publicDate": "2026-03-01",
                        },
                        {"code": "FPT", "eventType": "AGM"},  # no date → skipped
                    ]
                },
            )

        rows = _provider(handler).fetch_events(["FPT"], since=date(2026, 1, 1))
        assert len(rows) == 1
        assert isinstance(rows[0], EventRow)
        assert rows[0].event_type == "DIVIDEND"
        assert rows[0].event_date == date(2026, 3, 15)
        assert rows[0].announced_date == date(2026, 3, 1)


class TestValidators:
    def test_quarter_bounds_and_period_type(self) -> None:
        bad = FinancialRow(
            symbol="FPT",
            period_type="QUARTER",
            fiscal_year=2024,
            fiscal_period=7,
            statement_type="INCOME",
            line_item="revenue",
            value=Decimal("1"),
            report_date=date(2024, 6, 30),
        )
        codes = {(i.dataset, i.field) for i in validate_financials([bad])}
        assert ("financials", "fiscal_period") in codes

    def test_year_requires_zero_period(self) -> None:
        bad = FinancialRow(
            symbol="FPT",
            period_type="YEAR",
            fiscal_year=2024,
            fiscal_period=3,
            statement_type="INCOME",
            line_item="revenue",
            value=Decimal("1"),
            report_date=date(2024, 12, 31),
        )
        assert any(i.field == "fiscal_period" for i in validate_financials([bad]))

    def test_published_before_report_flagged(self) -> None:
        from datetime import datetime

        row = FinancialRow(
            symbol="FPT",
            period_type="QUARTER",
            fiscal_year=2024,
            fiscal_period=2,
            statement_type="INCOME",
            line_item="revenue",
            value=Decimal("1"),
            report_date=date(2024, 6, 30),
            published_at=datetime(2024, 5, 1),
        )
        assert any(i.field == "published_at" for i in validate_financials([row]))

    def test_events_announced_after_event_flagged(self) -> None:
        row = EventRow(
            symbol="FPT",
            event_type="DIVIDEND",
            event_date=date(2026, 3, 1),
            announced_date=date(2026, 3, 5),
        )
        assert any(
            i.field == "announced_date" for i in validate_events([row], since=date(2026, 1, 1))
        )


class TestFixtureProviderFinancials:
    def test_fixture_serves_financials_and_events(self) -> None:
        from src.data.providers.fixture import build_fixture_provider

        provider = build_fixture_provider(
            symbols=["FPT", "VCB"],
            start=date(2026, 1, 1),
            end=date(2026, 9, 30),
            include_financials=True,
            include_events=True,
        )
        assert provider.supports("financials")
        assert provider.supports("events")

        rows = provider.fetch_financials(["FPT"], period_types=("QUARTER",))
        assert rows and all(r.symbol == "FPT" for r in rows)
        # Fixture policy: publication = quarter end + 45 days (a real boundary).
        revenue = next(r for r in rows if r.line_item == "revenue")
        assert revenue.published_at is not None
        assert revenue.published_at.date() > revenue.report_date

        events = provider.fetch_events(["FPT", "VCB"], since=date(2026, 1, 1))
        assert {e.symbol for e in events} == {"FPT", "VCB"}

    def test_fixture_without_financials_does_not_support_dataset(self) -> None:
        from src.data.providers.fixture import build_fixture_provider

        provider = build_fixture_provider(
            symbols=["FPT"], start=date(2026, 1, 1), end=date(2026, 1, 31)
        )
        assert not provider.supports("financials")
        assert not provider.supports("events")


class TestProviderChain:
    def test_fundamental_chain_prefers_verified_cafef(self) -> None:
        from src.data.providers.registry import financial_provider_chain, get_spec

        chain = financial_provider_chain()
        assert chain[0] == "cafef_financials"  # the only VERIFIED source
        assert "vndirect_financials" in chain  # kept as the fallback

        spec = get_spec("cafef_financials")
        assert "fundamental" in spec.roles
        assert spec.endpoints["fundamental"]["client"] == "cafef_financial"
        assert spec.endpoints["fundamental"]["statements"]["INCOME"]["report_type"] == "KQKD"

    def test_create_provider_builds_cafef_financial_provider(self) -> None:
        from src.data.providers.cafef_financials import CafefFinancialProvider
        from src.data.providers.registry import create_provider

        provider = create_provider("cafef_financials")
        assert isinstance(provider, CafefFinancialProvider)
        assert provider.supports("financials")

    def test_create_provider_builds_financial_provider(self) -> None:
        from src.data.providers.registry import create_provider

        provider = create_provider("vndirect_financials")
        assert isinstance(provider, VNDirectFinancialProvider)
