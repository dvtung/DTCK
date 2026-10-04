"""CafeF `apiweb` provider — real quarterly/annual financial statements (§5.1).

**Verified reachable from the dev host on 2026-10-03** (the first source in this
project that answers with real Vietnamese BCTC):

* ``GET https://apiweb.cafef.vn/api/v2/BCTC/GetReportCDKT`` — balance sheet
  (``reportType=ALL``)
* ``GET https://apiweb.cafef.vn/api/v1/BCTC/GetReportDetail`` — income statement
  (``reportType=KQKD``)
* ``GET https://apiweb.cafef.vn/api/v1/BCTC/GetReportLCTT`` — cash flow
  (``reportType=ALL``)

Shared query: ``symbol``, ``pageIndex``, ``pageSize``, ``reportType``,
``TypeTime=QUY|NAM``. Recorded payload:
``tests/fixtures/cafef_financials_sample.json``.

Shape notes (encoded here because they drive the parser):

* response is ``{isSuccess, value: {templace, data, count, unit}}``;
* ``templace`` carries the VAS line-item catalogue (``code`` → Vietnamese
  ``name``) — either flat or grouped into sections;
* ``value.data`` is **grouped** for balance sheet/cash flow
  (``[{code, name, number, data: [periods]}]``) but **flat** for the income
  statement (``[periods]``); a period entry is
  ``{symbol, year, quater, type, content, time, data: [{code, value}]}``;
* ``time`` is ``"Q2-2026"`` (quarterly) or ``"2025"`` (annual), and ``quater``
  is ``0`` for annual rows;
* ``content`` holds the audit remark (e.g. ``"Đã kiểm toán"``) — a useful red
  flag input for GĐ 4, currently not persisted (no column in
  ``financial_statements`` yet);
* **no publication date** is returned → ``published_at`` is stored ``NULL``
  (honest: never guessed, spec §31).
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from src.data.providers.base import DataProvider
from src.data.providers.rss import DEFAULT_USER_AGENT
from src.data.records import FinancialRow

logger = logging.getLogger(__name__)

#: statement_type -> (endpoint path, reportType). Overridable via config.
DEFAULT_STATEMENT_ENDPOINTS: dict[str, dict[str, str]] = {
    "BALANCE": {"path": "api/v2/BCTC/GetReportCDKT", "report_type": "ALL"},
    "INCOME": {"path": "api/v1/BCTC/GetReportDetail", "report_type": "KQKD"},
    "CASHFLOW": {"path": "api/v1/BCTC/GetReportLCTT", "report_type": "ALL"},
}
DEFAULT_CAFEF_ORIGIN = "https://apiweb.cafef.vn"

_QUARTER_END_MONTH = {1: 3, 2: 6, 3: 9, 4: 12}
_QUARTER_END_DAY = {3: 31, 6: 30, 9: 30, 12: 31}


def _report_date(year: int, quarter: int, period_type: str) -> date:
    if period_type == "YEAR":
        return date(year, 12, 31)
    month = _QUARTER_END_MONTH.get(quarter, 3)
    return date(year, month, _QUARTER_END_DAY[month])


def _parse_period(entry: dict[str, Any]) -> tuple[str, int, int] | None:
    """``(period_type, fiscal_year, fiscal_period)`` for one period entry."""
    raw_time = str(entry.get("time") or "")
    year = entry.get("year")
    quarter = entry.get("quater")
    if year is None:
        return None
    if raw_time.startswith("Q") and "-" in raw_time:
        # "Q2-2026"
        try:
            period = int(raw_time[1:].split("-", 1)[0])
        except ValueError:
            return None
        return "QUARTER", int(year), period
    return "YEAR", int(year), int(quarter or 0)


def _iter_period_entries(data: Any) -> list[dict[str, Any]]:
    """Flatten grouped (balance/cash-flow) and flat (income) payload shapes."""
    if not isinstance(data, list):
        return []
    entries: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if "time" in item:
            entries.append(item)
        elif isinstance(item.get("data"), list):
            for inner in item["data"]:
                if isinstance(inner, dict) and "time" in inner:
                    entries.append(inner)
    return entries


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


class CafefFinancialProvider(DataProvider):
    """Quarterly/annual financial statements from CafeF's public ``apiweb``."""

    id: str = "cafef_financials"
    SUPPORTED_DATASETS = frozenset({"financials"})

    def __init__(
        self,
        *,
        provider_id: str = "cafef_financials",
        origin: str | None = None,
        endpoints: dict[str, dict[str, str]] | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout_s: float = 30.0,
        page_size: int = 20,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.id = provider_id
        self._origin = (origin or DEFAULT_CAFEF_ORIGIN).rstrip("/")
        self._endpoints = endpoints or DEFAULT_STATEMENT_ENDPOINTS
        self._transport = transport
        self._timeout_s = timeout_s
        self._page_size = page_size
        self._user_agent = user_agent

    # ------------------------------------------------------------- transport
    def _client(self) -> httpx.Client:
        return httpx.Client(
            transport=self._transport,
            timeout=self._timeout_s,
            headers={"User-Agent": self._user_agent, "Accept": "application/json"},
            follow_redirects=True,
        )

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._origin}/{path.lstrip('/')}"
        with self._client() as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(f"provider '{self.id}': malformed payload for {path}")
        if payload.get("isSuccess") is False:
            raise ValueError(
                f"provider '{self.id}': apiweb reported errors: {payload.get('errors')}"
            )
        return payload

    # ----------------------------------------------------------- financials
    def fetch_financials(
        self, symbols: list[str], *, period_types: tuple[str, ...] = ("QUARTER", "YEAR")
    ) -> list[FinancialRow]:
        """Fetch balance/income/cash-flow line items for ``symbols``."""
        rows: list[FinancialRow] = []
        for symbol in symbols:
            for period_type in period_types:
                type_time = "QUY" if period_type == "QUARTER" else "NAM"
                for statement_type, endpoint in self._endpoints.items():
                    params = {
                        "symbol": symbol.upper(),
                        "pageIndex": 1,
                        "pageSize": self._page_size,
                        "reportType": endpoint["report_type"],
                        "TypeTime": type_time,
                    }
                    payload = self._get(endpoint["path"], params)
                    rows.extend(
                        self._map_rows(payload, symbol.upper(), statement_type, period_type)
                    )
        return rows

    def _map_rows(
        self,
        payload: dict[str, Any],
        symbol: str,
        statement_type: str,
        period_type: str,
    ) -> list[FinancialRow]:
        value = payload.get("value")
        if not isinstance(value, dict):
            raise ValueError(f"provider '{self.id}': payload has no 'value' object")
        rows: list[FinancialRow] = []
        for entry in _iter_period_entries(value.get("data")):
            rows.extend(
                self._map_entry(entry, symbol, statement_type, period_type)
            )
        return rows

    def _map_entry(
        self,
        entry: dict[str, Any],
        symbol: str,
        statement_type: str,
        period_type: str,
    ) -> list[FinancialRow]:
        parsed = _parse_period(entry)
        if parsed is None:
            return []
        row_period_type, fiscal_year, fiscal_period = parsed
        if row_period_type != period_type:
            return []  # requested QUY but the payload only carries NAM (or vice versa)
        report_date = _report_date(fiscal_year, fiscal_period, row_period_type)
        rows: list[FinancialRow] = []
        for item in entry.get("data") or []:
            if not isinstance(item, dict):
                continue
            line_item = item.get("code")
            value = _to_decimal(item.get("value"))
            if line_item is None or value is None:
                continue  # missing item/value → skip, never zero-filled
            rows.append(
                FinancialRow(
                    symbol=symbol,
                    period_type=row_period_type,
                    fiscal_year=fiscal_year,
                    fiscal_period=fiscal_period if row_period_type == "QUARTER" else 0,
                    statement_type=statement_type,
                    line_item=str(line_item),
                    value=value,
                    report_date=report_date,
                    # CafeF discloses no filing timestamp → NULL, never guessed.
                    published_at=None,
                )
            )
        return rows


__all__ = [
    "CafefFinancialProvider",
    "DEFAULT_CAFEF_ORIGIN",
    "DEFAULT_STATEMENT_ENDPOINTS",
]
