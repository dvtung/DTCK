"""SSI FastConnect Market Data API provider.

Implements the official SSI FastConnect Data API v2 (https://fc-data.ssi.com.vn)
supporting EOD stock prices (`Market/DailyOhlc`) and index prices (`Market/DailyIndex`).
Authentication uses ConsumerID and ConsumerSecret via `Market/AccessToken` to obtain
a Bearer token, which is cached until expiration.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from src.data.providers.base import DataProvider
from src.data.records import EODBar, IndexBar

logger = logging.getLogger(__name__)

DEFAULT_SSI_API_URL = "https://fc-data.ssi.com.vn"
DEFAULT_USER_AGENT = "DTCK/0.1 (+https://github.com/dvtung/DTCK)"


def _format_date(d: date) -> str:
    """Format date as DD/MM/YYYY for SSI FastConnect API."""
    return d.strftime("%d/%m/%Y")


def _parse_date(s: str) -> date:
    """Parse DD/MM/YYYY or YYYY-MM-DD date string."""
    s = s.strip()
    if "/" in s:
        parts = s.split("/")
        if len(parts) == 3:
            return date(int(parts[2]), int(parts[1]), int(parts[0]))
    return date.fromisoformat(s)


class SSIFastConnectProvider(DataProvider):
    """Data provider for SSI FastConnect Data API v2.

    Supports both stock EOD prices (`fetch_eod`) and index prices (`fetch_index`).
    Handles authentication via `POST /api/v2/Market/AccessToken` with token caching.
    """

    id: str = "ssi_fastconnect"
    SUPPORTED_DATASETS = frozenset({"prices", "index_prices"})

    def __init__(
        self,
        *,
        provider_id: str = "ssi_fastconnect",
        consumer_id: str | None = None,
        consumer_secret: str | None = None,
        api_url: str | None = None,
        access_token: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff: float = 2.0,
        transport: Any | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.id = provider_id
        self._consumer_id = (
            consumer_id if consumer_id is not None else os.getenv("SSI_CONSUMER_ID", "")
        )
        self._consumer_secret = (
            consumer_secret if consumer_secret is not None else os.getenv("SSI_CONSUMER_SECRET", "")
        )
        self._api_url = (
            api_url if api_url is not None else os.getenv("SSI_API_URL", DEFAULT_SSI_API_URL)
        ).rstrip("/")
        self._cached_token = (
            access_token if access_token is not None else os.getenv("FINIPRO_ACCESS_TOKEN", "")
        ) or None
        self._token_expires_at: float | None = 1e12 if self._cached_token else None
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        self._transport = transport
        self._user_agent = user_agent

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=self._timeout, transport=self._transport)

    def get_access_token(self, force_refresh: bool = False) -> str:
        """Obtain or return cached Bearer access token."""
        now = time.time()
        if (
            not force_refresh
            and self._cached_token
            and self._token_expires_at
            and now < self._token_expires_at - 60
        ):
            return self._cached_token

        if not self._consumer_id or not self._consumer_secret:
            if self._cached_token:
                return self._cached_token
            raise ValueError(
                f"provider '{self.id}': missing SSI_CONSUMER_ID or SSI_CONSUMER_SECRET"
            )

        token_url = f"{self._api_url}/api/v2/Market/AccessToken"
        payload = {
            "consumerID": self._consumer_id,
            "consumerSecret": self._consumer_secret,
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": self._user_agent,
        }

        with self._client() as client:
            resp = client.post(token_url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        status = data.get("status")
        if status not in (200, "200", "Success", "OK"):
            msg = data.get("message", "Authentication failed")
            raise ConnectionError(f"provider '{self.id}': failed to get access token: {msg}")

        token_data = data.get("data") or {}
        token = token_data.get("accessToken")
        if not token:
            raise ValueError(f"provider '{self.id}': response missing accessToken: {data}")

        self._cached_token = str(token)
        # FastConnect tokens expire in ~8 hours; cache for 6 hours
        self._token_expires_at = now + (6 * 3600)
        return str(token)

    def _request_with_retry(
        self, endpoint: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Make an authenticated GET request with token refresh on 401 and retry backoff."""
        url = f"{self._api_url}/{endpoint.lstrip('/')}"
        token = self.get_access_token()

        for attempt in range(self._max_retries + 1):
            headers = {
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "User-Agent": self._user_agent,
            }
            try:
                with self._client() as client:
                    resp = client.get(url, params=params, headers=headers)
                    if resp.status_code == 401 and attempt < self._max_retries:
                        logger.warning(
                            "SSI API 401 Unauthorized — refreshing token and retrying (attempt %d)",
                            attempt + 1,
                        )
                        token = self.get_access_token(force_refresh=True)
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    if isinstance(data, dict):
                        return data
                    raise ValueError(f"expected dict response, got {type(data)}")
            except (httpx.HTTPError, ValueError) as exc:
                if attempt >= self._max_retries:
                    raise ConnectionError(
                        f"provider '{self.id}' failed after {self._max_retries + 1} attempts: {exc}"
                    ) from exc
                time.sleep(min(self._retry_backoff * (attempt + 1), 30.0))

        raise ConnectionError(f"provider '{self.id}': request failed for {endpoint}")

    def fetch_index_components(self, index_code: str) -> list[dict[str, str]]:
        """Fetch constituent stocks of an index (e.g. 'VN100', 'VN30', 'HNX30').

        Returns a list of dicts with keys: ``{"symbol": ..., "isin": ...}``.
        """
        params = {
            "indexCode": index_code.strip().upper(),
            "pageIndex": 1,
            "pageSize": 1000,
        }
        resp = self._request_with_retry("api/v2/Market/IndexComponents", params)
        data = resp.get("data") or []
        if not data:
            return []
        items = data[0].get("IndexComponent") or []
        out: list[dict[str, str]] = []
        for it in items:
            sym = str(it.get("StockSymbol") or "").strip().upper()
            if sym:
                out.append({"symbol": sym, "isin": str(it.get("Isin") or "")})
        return out

    def fetch_eod(self, symbols: list[str], start: date, end: date) -> list[EODBar]:
        """Fetch daily OHLCV bars for given symbols within [start, end]."""
        bars: list[EODBar] = []
        from_date_str = _format_date(start)
        to_date_str = _format_date(end)

        for sym in symbols:
            symbol_clean = sym.strip().upper()
            page_index = 1
            page_size = 1000

            while True:
                params = {
                    "symbol": symbol_clean,
                    "fromDate": from_date_str,
                    "toDate": to_date_str,
                    "pageIndex": page_index,
                    "pageSize": page_size,
                    "ascending": "true",
                }
                resp_data = self._request_with_retry("api/v2/Market/DailyOhlc", params)
                rows = resp_data.get("data") or []
                if not rows:
                    break

                for row in rows:
                    try:
                        trade_date = _parse_date(str(row["TradingDate"]))
                        if trade_date < start or trade_date > end:
                            continue

                        market = str(row.get("Market") or "HOSE").upper()
                        open_val = Decimal(str(row["Open"]))
                        high_val = Decimal(str(row["High"]))
                        low_val = Decimal(str(row["Low"]))
                        close_val = Decimal(str(row["Close"]))
                        volume_val = int(Decimal(str(row.get("Volume", 0))))
                        val_str = row.get("Value")
                        if val_str is not None:
                            trading_value = Decimal(str(val_str))
                        else:
                            trading_value = close_val * Decimal(volume_val)

                        bars.append(
                            EODBar(
                                symbol=symbol_clean,
                                exchange=market,
                                trade_date=trade_date,
                                open=open_val,
                                high=high_val,
                                low=low_val,
                                close=close_val,
                                volume=volume_val,
                                trading_value=trading_value,
                            )
                        )
                    except (KeyError, TypeError, InvalidOperation, ValueError) as exc:
                        raise ValueError(
                            f"provider '{self.id}': unmappable EOD row {row!r}: {exc}"
                        ) from exc

                total_record = resp_data.get("totalRecord")
                if total_record is not None:
                    try:
                        if page_index * page_size >= int(total_record):
                            break
                    except (ValueError, TypeError):
                        pass

                if len(rows) < page_size:
                    break
                page_index += 1

        return bars

    def fetch_index(
        self, index_codes: list[str], start: date, end: date
    ) -> list[IndexBar]:
        """Fetch index daily OHLCV bars for given index codes within [start, end].

        Note: SSI DailyIndex API rejects queries with date windows exceeding ~30-60 days.
        To support multi-year backfills, queries spanning > 30 days are automatically chunked.
        """
        from datetime import timedelta

        if (end - start).days > 30:
            all_bars: list[IndexBar] = []
            curr_start = start
            while curr_start <= end:
                curr_end = min(curr_start + timedelta(days=30), end)
                sub_bars = self._fetch_index_sub_window(index_codes, curr_start, curr_end)
                all_bars.extend(sub_bars)
                curr_start = curr_end + timedelta(days=1)
            # Deduplicate by (index_code, trade_date)
            seen_index: set[tuple[str, date]] = set()
            unique_bars: list[IndexBar] = []
            for b in all_bars:
                k = (b.index_code, b.trade_date)
                if k not in seen_index:
                    seen_index.add(k)
                    unique_bars.append(b)
            return sorted(unique_bars, key=lambda x: (x.index_code, x.trade_date))

        return self._fetch_index_sub_window(index_codes, start, end)

    def _fetch_index_sub_window(
        self, index_codes: list[str], start: date, end: date
    ) -> list[IndexBar]:
        bars: list[IndexBar] = []
        from_date_str = _format_date(start)
        to_date_str = _format_date(end)

        for index_code in index_codes:
            code_clean = index_code.strip().upper()
            page_index = 1
            page_size = 1000

            while True:
                params = {
                    "indexId": code_clean,
                    "fromDate": from_date_str,
                    "toDate": to_date_str,
                    "pageIndex": page_index,
                    "pageSize": page_size,
                    "order": "asc",
                }
                resp_data = self._request_with_retry("api/v2/Market/DailyIndex", params)
                rows = resp_data.get("data") or []
                if not rows:
                    break

                for row in rows:
                    try:
                        trade_date = _parse_date(str(row["TradingDate"]))
                        if trade_date < start or trade_date > end:
                            continue

                        close_val = Decimal(str(row.get("IndexValue", 0)))
                        open_val = Decimal(str(row.get("Open") or close_val))
                        high_val = Decimal(str(row.get("High") or close_val))
                        low_val = Decimal(str(row.get("Low") or close_val))

                        vol_val = row.get("TotalMatchVol") or row.get("TotalVol") or 0
                        val_val = row.get("TotalMatchVal") or row.get("TotalVal") or 0
                        volume = int(Decimal(str(vol_val)))
                        trading_value = Decimal(str(val_val))

                        bars.append(
                            IndexBar(
                                index_code=code_clean,
                                trade_date=trade_date,
                                open=open_val,
                                high=high_val,
                                low=low_val,
                                close=close_val,
                                volume=volume,
                                trading_value=trading_value,
                            )
                        )
                    except (KeyError, TypeError, InvalidOperation, ValueError) as exc:
                        raise ValueError(
                            f"provider '{self.id}': unmappable Index row {row!r}: {exc}"
                        ) from exc

                total_record = resp_data.get("totalRecord")
                if total_record is not None:
                    try:
                        if page_index * page_size >= int(total_record):
                            break
                    except (ValueError, TypeError):
                        pass

                if len(rows) < page_size:
                    break
                page_index += 1

        return bars


__all__ = ["SSIFastConnectProvider", "DEFAULT_SSI_API_URL"]
