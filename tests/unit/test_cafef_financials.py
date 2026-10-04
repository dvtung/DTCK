"""Unit tests for the CafeF financial-statements provider (recorded payload)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from src.data.providers.cafef_financials import CafefFinancialProvider

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "cafef_financials_sample.json"
PAYLOADS = json.loads(FIXTURE.read_text(encoding="utf-8"))

_PATH_TO_KEY = {
    "GetReportCDKT": "balance_sheet",
    "GetReportDetail": "income_statement",
    "GetReportLCTT": "cash_flow",
}


def _handler(request: httpx.Request) -> httpx.Response:
    for marker, key in _PATH_TO_KEY.items():
        if marker in request.url.path:
            return httpx.Response(200, json=PAYLOADS[key])
    return httpx.Response(404, json={"isSuccess": False, "errors": ["unknown path"]})


def _provider() -> CafefFinancialProvider:
    return CafefFinancialProvider(transport=httpx.MockTransport(_handler), timeout_s=5.0)


class TestCafefMapping:
    def test_quarter_rows_from_all_three_statements(self) -> None:
        rows = _provider().fetch_financials(["FPT"], period_types=("QUARTER",))
        assert rows, "recorded payload must yield rows"
        assert {r.statement_type for r in rows} == {"BALANCE", "INCOME", "CASHFLOW"}
        assert all(r.period_type == "QUARTER" for r in rows)
        assert all(r.symbol == "FPT" for r in rows)

    def test_income_revenue_is_real_number(self) -> None:
        rows = _provider().fetch_financials(["FPT"], period_types=("QUARTER",))
        revenue = next(
            r
            for r in rows
            if r.statement_type == "INCOME"
            and r.line_item == "10"
            and r.fiscal_year == 2026
            and r.fiscal_period == 2
        )
        # FPT net revenue Q2-2026 from the recorded payload.
        assert revenue.value == 13788503461199
        assert revenue.report_date == date(2026, 6, 30)

    def test_balance_sheet_grouped_shape_is_flattened(self) -> None:
        rows = _provider().fetch_financials(["FPT"], period_types=("QUARTER",))
        q2 = [
            r
            for r in rows
            if r.statement_type == "BALANCE" and r.fiscal_period == 2 and r.fiscal_year == 2026
        ]
        by_code = {r.line_item: r.value for r in q2}
        # Grouped payload (groups "TN"/"NV" each carrying period entries).
        assert by_code["100"] == 45701998651416  # A. TÀI SẢN NGẮN HẠN
        assert by_code["270"] == 73734163085489  # TỔNG CỘNG TÀI SẢN

    def test_annual_period_maps_to_year_with_zero_quarter(self) -> None:
        """A NAM payload maps to period_type YEAR with fiscal_period 0.

        The recorded fixture is quarterly only, so the honest outcome for a
        YEAR request against it is an empty list (rows of the wrong period are
        rejected, never relabelled).
        """
        rows = _provider().fetch_financials(["FPT"], period_types=("YEAR",))
        assert rows == []

    def test_synthetic_annual_row_is_mapped(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "isSuccess": True,
                    "value": {
                        "data": [
                            {
                                "symbol": "FPT",
                                "year": 2025,
                                "quater": 0,
                                "type": "HK",
                                "content": "Đã kiểm toán",
                                "time": "2025",
                                "data": [{"code": "10", "value": 70112825100710}],
                            }
                        ]
                    },
                },
            )

        provider = CafefFinancialProvider(
            transport=httpx.MockTransport(handler), timeout_s=5.0
        )
        rows = provider.fetch_financials(["FPT"], period_types=("YEAR",))
        # One row per statement endpoint (3 endpoints all answer the same payload).
        assert len(rows) == 3
        assert {r.statement_type for r in rows} == {"BALANCE", "INCOME", "CASHFLOW"}
        assert all(r.period_type == "YEAR" for r in rows)
        assert all(r.fiscal_period == 0 for r in rows)
        assert all(r.fiscal_year == 2025 for r in rows)
        assert all(r.report_date == date(2025, 12, 31) for r in rows)

    def test_published_at_is_always_none(self) -> None:
        """CafeF discloses no filing timestamp — never invent one (§31)."""
        rows = _provider().fetch_financials(["FPT"], period_types=("QUARTER",))
        assert rows
        assert all(r.published_at is None for r in rows)

    def test_missing_value_is_skipped_not_zero_filled(self) -> None:
        payload = {
            "isSuccess": True,
            "value": {
                "data": [
                    {
                        "symbol": "FPT",
                        "year": 2026,
                        "quater": 1,
                        "time": "Q1-2026",
                        "data": [
                            {"code": "10", "value": 100},
                            {"code": "11"},  # no value → must be skipped
                        ],
                    }
                ]
            },
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=payload)

        provider = CafefFinancialProvider(
            transport=httpx.MockTransport(handler), timeout_s=5.0
        )
        rows = provider.fetch_financials(["FPT"], period_types=("QUARTER",))
        codes = {r.line_item for r in rows}
        assert codes == {"10"}

    def test_is_success_false_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"isSuccess": False, "errors": ["boom"]})

        provider = CafefFinancialProvider(
            transport=httpx.MockTransport(handler), timeout_s=5.0
        )
        with pytest.raises(ValueError, match="apiweb reported errors"):
            provider.fetch_financials(["FPT"], period_types=("QUARTER",))

    def test_supported_datasets(self) -> None:
        provider = _provider()
        assert provider.supports("financials")
        assert not provider.supports("prices")


class TestCafefRegistry:
    def test_create_provider_uses_configured_endpoints(self) -> None:
        from src.data.providers.registry import create_provider

        provider = create_provider("cafef_financials")
        assert isinstance(provider, CafefFinancialProvider)
        # Config drives the statement endpoints (nothing hard-coded in the class).
        assert provider._endpoints["INCOME"]["path"].endswith("GetReportDetail")

    def test_live_flow_uses_https_origin_by_default(self) -> None:
        provider = CafefFinancialProvider()
        assert provider._origin == "https://apiweb.cafef.vn"
