"""Configurable JSON-over-HTTP provider for EOD market data (T004).

The endpoint contract lives in ``configs/sources.yaml`` per provider (``endpoints.eod``):
a URL, query-param templates, the JSON list path and a field mapping. Endpoints are
**TO VERIFY** (KI-006) until snapshot-tested against the real vendor — the mapping
below is declarative so verifying a provider is a config change, not a code change.

Retry/backoff follows the registry ``defaults`` block (§8.1 error handling).
"""

from __future__ import annotations

import time
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from src.data.providers.base import DataProvider
from src.data.records import EODBar


def _format(value: Any, spec: dict[str, Any]) -> str:
    if isinstance(value, date):
        return value.strftime(str(spec.get("date_format", "%Y-%m-%d")))
    return str(value)


def _substitute(template: str, mapping: dict[str, str]) -> str:
    out = template
    for key, value in mapping.items():
        out = out.replace(key, value)
    return out


def _dig(payload: Any, dotted: str) -> Any:
    """Walk a dotted path (e.g. ``data.items``) inside a JSON payload."""
    node: Any = payload
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(f"response field path '{dotted}' not found (missing '{part}')")
        node = node[part]
    return node


def _as_decimal(value: Any) -> Decimal:
    if value is None:
        raise ValueError("missing numeric value")
    return Decimal(str(value))


def _as_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    text = str(value)
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unparseable date: {value!r}")


class HttpJsonProvider(DataProvider):
    """Fetches EOD OHLCV from a configurable JSON endpoint."""

    id: str

    def __init__(
        self,
        *,
        provider_id: str,
        eod_config: dict[str, Any],
        timeout: float,
        max_retries: int,
        retry_backoff: float,
        credential: str | None = None,
        auth: str = "none",
        transport: Any | None = None,
    ) -> None:
        self.id = provider_id
        self._cfg = eod_config
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        self._credential = credential
        self._auth = auth
        self._transport = transport  # injectable for tests (httpx.MockTransport)
        self.SUPPORTED_DATASETS = frozenset({"prices"})

    # --- request building -----------------------------------------------------------------

    def _build_request(self, symbol: str, start: date, end: date) -> httpx.Request:
        cfg = self._cfg
        mapping = {
            "{symbol}": symbol.upper(),
            "{start}": _format(start, cfg),
            "{end}": _format(end, cfg),
        }
        url = _substitute(str(cfg["url"]), mapping)
        params: dict[str, str] = {
            str(name): _substitute(str(template), mapping)
            for name, template in (cfg.get("params") or {}).items()
        }
        headers: dict[str, str] = {"Accept": "application/json"}
        if self._credential and self._auth == "bearer":
            headers["Authorization"] = f"Bearer {self._credential}"
        elif self._credential and self._auth == "query":
            params["apikey"] = self._credential
        headers.update(cfg.get("headers") or {})
        # Build the request standalone — creating (and discarding) a Client here
        # would leak an unclosed connection pool per call.
        return httpx.Request("GET", url, params=params, headers=headers)

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=self._timeout, transport=self._transport)

    def _get_json(self, symbol: str, start: date, end: date) -> Any:
        request = self._build_request(symbol, start, end)
        last_error: Exception | None = None
        with self._client() as client:
            for attempt in range(self._max_retries + 1):
                try:
                    response = client.send(request)
                    response.raise_for_status()
                    return response.json()
                except (httpx.HTTPError, ValueError) as exc:  # noqa: PERF203
                    last_error = exc
                    if attempt >= self._max_retries:
                        break
                    time.sleep(min(self._retry_backoff * (attempt + 1), 30))
            raise ConnectionError(
                f"provider '{self.id}' failed after {self._max_retries + 1} attempts: {last_error}"
            )

    # --- payload → records ----------------------------------------------------------------

    def _map_rows(self, payload: Any) -> list[EODBar]:
        cfg = self._cfg
        fields: dict[str, str] = cfg["fields"]
        rows = _dig(payload, str(cfg.get("list_path", "data")))
        if not isinstance(rows, list):
            raise ValueError(
                f"list_path '{cfg.get('list_path', 'data')}' did not resolve to a list"
            )

        bars: list[EODBar] = []
        for row in rows:
            try:
                bars.append(
                    EODBar(
                        symbol=str(row[fields["symbol"]]).upper(),
                        exchange=str(cfg.get("exchange", "HOSE")).upper(),
                        trade_date=_as_date(row[fields["trade_date"]]),
                        open=_as_decimal(row[fields["open"]]),
                        high=_as_decimal(row[fields["high"]]),
                        low=_as_decimal(row[fields["low"]]),
                        close=_as_decimal(row[fields["close"]]),
                        volume=int(row[fields["volume"]]),
                        trading_value=_as_decimal(row[fields["trading_value"]]),
                    )
                )
            except (KeyError, TypeError, InvalidOperation, ValueError) as exc:
                raise ValueError(
                    f"provider '{self.id}': unmappable EOD row {row!r}: {exc}"
                ) from exc
        return bars

    # --- DataProvider ---------------------------------------------------------------------

    def fetch_eod(self, symbols: list[str], start: date, end: date) -> list[EODBar]:
        bars: list[EODBar] = []
        for symbol in symbols:
            bars.extend(self._map_rows(self._get_json(symbol, start, end)))
        return [bar for bar in bars if start <= bar.trade_date <= end]

    def fetch_index(self, index_codes: list[str], start: date, end: date) -> list[Any]:
        raise NotImplementedError(f"provider '{self.id}' does not implement index_prices")

    def fetch_news(self, since: datetime) -> list[Any]:
        raise NotImplementedError(f"provider '{self.id}' does not implement news")


__all__ = ["HttpJsonProvider"]
