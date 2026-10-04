"""VNDirect finfo API provider — financial statements + corporate events (§5.1/§7.1).

Why VNDirect and not SSI: SSI's FastConnect **Data** API (``fc-data.ssi.com.vn``,
the one ``ssix_finipro`` uses) exposes **only market endpoints** — verified against
the official function list on 2026-10-03: ``AccessToken, Securities,
SecuritiesDetails, DailyOhlc, DailyIndex, IndexList, IndexComponents,
IntradayOhlc, DailyStockPrice``. Financial statements at SSI live in the separate
**iExcel** product (``IE.BalanceSheet/IE.IncomeStatement/IE.CashFlow``), which has
no REST API. So per the agreed fallback rule the fundamental role falls to
VNDirect's ``finfo`` service (already declared ``roles: [market, fundamental]``
in ``configs/sources.yaml``).

**Honesty note (KI-006 continued):** ``finfo-api.vndirect.com.vn`` did **not
answer** from the development host on 2026-10-03 (TCP connect timeout), so the
live payload shape is still ``TO VERIFY``. The mapping below is therefore written
*defensively* — it accepts several documented key spellings and never invents a
value: a missing ``published_at`` stays ``None`` (stored NULL), a missing numeric
item is skipped rather than zero-filled. Offline tests pin behaviour against a
recorded fixture (``tests/fixtures/vndirect_financials_sample.json``).
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from src.data.providers.base import DataProvider
from src.data.providers.rss import DEFAULT_USER_AGENT
from src.data.records import EventRow, FinancialRow

logger = logging.getLogger(__name__)

DEFAULT_VNDIRECT_FINFO_URL = "https://finfo-api.vndirect.com.vn/v4"

#: finfo ``modelType`` → our ``statement_type`` (§5.1 vocab).
_MODEL_TYPE_TO_STATEMENT = {"1": "INCOME", "2": "BALANCE", "3": "CASHFLOW"}
_STATEMENT_TO_MODEL_TYPE = {v: k for k, v in _MODEL_TYPE_TO_STATEMENT.items()}

#: Candidate key spellings for the incoming payload (tolerant to vendor drift).
_SYMBOL_KEYS = ("code", "symbol", "ticker")
_PUBLISHED_KEYS = ("publicDate", "publishedAt", "createdDate", "created_at")


def _first(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value).strip().replace("/", "-")
    if "T" in text:
        text = text.split("T", 1)[0]
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if "T" in text:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    parsed = _parse_date(value)
    return datetime(parsed.year, parsed.month, parsed.day) if parsed else None


def _quarter_from_month(month: int) -> int:
    return (month - 1) // 3 + 1


class VNDirectFinancialProvider(DataProvider):
    """Financial statements + corporate events from VNDirect's finfo service."""

    id: str = "vndirect_financials"
    SUPPORTED_DATASETS = frozenset({"financials", "events"})

    def __init__(
        self,
        *,
        provider_id: str = "vndirect_financials",
        base_url: str | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout_s: float = 30.0,
        page_size: int = 500,
    ) -> None:
        self.id = provider_id
        self._base_url = (base_url or DEFAULT_VNDIRECT_FINFO_URL).rstrip("/")
        self._transport = transport
        self._timeout_s = timeout_s
        self._page_size = page_size

    # ------------------------------------------------------------- transport
    def _client(self) -> httpx.Client:
        return httpx.Client(
            transport=self._transport,
            timeout=self._timeout_s,
            headers={"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
        )

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}/{path.lstrip('/')}"
        with self._client() as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(f"provider '{self.id}': malformed payload for {path}")
        return payload

    # ----------------------------------------------------------- financials
    def fetch_financials(
        self, symbols: list[str], *, period_types: tuple[str, ...] = ("QUARTER", "YEAR")
    ) -> list[FinancialRow]:
        """Fetch line items for ``symbols`` across the requested period types."""
        rows: list[FinancialRow] = []
        for symbol in symbols:
            for report_type in period_types:
                for statement_type, model_type in _STATEMENT_TO_MODEL_TYPE.items():
                    params = {
                        "q": (
                            f"code:{symbol.upper()}~reportType:{report_type}"
                            f"~modelType:{model_type}"
                        ),
                        "size": self._page_size,
                    }
                    payload = self._get("financial_statements", params)
                    rows.extend(
                        self._map_financial_rows(
                            payload, symbol.upper(), report_type, statement_type
                        )
                    )
        return rows

    def _map_financial_rows(
        self,
        payload: dict[str, Any],
        symbol: str,
        report_type: str,
        statement_type: str,
    ) -> list[FinancialRow]:
        items = payload.get("data")
        if not isinstance(items, list):
            raise ValueError(f"provider '{self.id}': payload 'data' is not a list")
        rows: list[FinancialRow] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            row = self._map_financial_row(item, symbol, report_type, statement_type)
            if row is not None:
                rows.append(row)
        return rows

    def _map_financial_row(
        self,
        item: dict[str, Any],
        symbol: str,
        report_type: str,
        statement_type: str,
    ) -> FinancialRow | None:
        report_date = _parse_date(item.get("fiscalDate") or item.get("reportDate"))
        line_item = _first(item, ("itemCode", "item_code", "line_item", "itemName"))
        value = _to_decimal(_first(item, ("numericValue", "value", "amount")))
        if report_date is None or line_item is None or value is None:
            # Missing period/item/value → nothing honest to store (skip, never zero).
            return None
        period_type = "YEAR" if str(report_type).upper().startswith("Y") else "QUARTER"
        return FinancialRow(
            symbol=str(_first(item, _SYMBOL_KEYS) or symbol).upper(),
            period_type=period_type,
            fiscal_year=report_date.year,
            fiscal_period=0 if period_type == "YEAR" else _quarter_from_month(report_date.month),
            statement_type=statement_type,
            line_item=str(line_item),
            value=value,
            report_date=report_date,
            published_at=_parse_datetime(_first(item, _PUBLISHED_KEYS)),
        )

    # --------------------------------------------------------------- events
    def fetch_events(self, symbols: list[str], *, since: date) -> list[EventRow]:
        """Fetch corporate events on/after ``since`` for ``symbols``."""
        rows: list[EventRow] = []
        for symbol in symbols:
            params = {
                "q": f"code:{symbol.upper()}~date:gte:{since.isoformat()}",
                "size": self._page_size,
            }
            payload = self._get("events", params)
            rows.extend(self._map_event_rows(payload, symbol.upper()))
        return rows

    def _map_event_rows(self, payload: dict[str, Any], symbol: str) -> list[EventRow]:
        items = payload.get("data")
        if not isinstance(items, list):
            raise ValueError(f"provider '{self.id}': payload 'data' is not a list")
        rows: list[EventRow] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            event_date = _parse_date(item.get("date") or item.get("eventDate"))
            if event_date is None:
                continue
            event_type = str(_first(item, ("eventType", "type", "group")) or "OTHER").upper()
            rows.append(
                EventRow(
                    symbol=str(_first(item, _SYMBOL_KEYS) or symbol).upper(),
                    event_type=event_type,
                    event_date=event_date,
                    announced_date=_parse_date(_first(item, ("publicDate", "announcedDate"))),
                    details={k: v for k, v in item.items() if v is not None},
                )
            )
        return rows


__all__ = ["DEFAULT_VNDIRECT_FINFO_URL", "VNDirectFinancialProvider"]
