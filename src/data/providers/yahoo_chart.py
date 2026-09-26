"""Yahoo Finance chart provider — public Vietnam EOD prices (T004 fallback).

Verified reachable from the project host on 2026-09-25 while the documented
market fallbacks are not (``configs/sources.yaml``: VNDirect DNS resolves to a
private address, TCBS sits behind a Cloudflare challenge, SSI FiniPro needs a
token). The v8 chart endpoint answers ``200`` for ``.VN`` tickers across
HOSE/HNX/UPCOM **only with a descriptive User-Agent** — the default python-httpx
agent receives ``429``.

Data-shape facts encoded here (recorded sample:
``tests/fixtures/yahoo_chart_sample.json``):

* **Split-adjusted series** — ``quote`` OHLC is divided by every split ratio
  after the bar and ``volume`` is multiplied by it (evidence: FPT's 11:10 split
  on 2026-09-21). The provider un-adjusts with ``events=split`` from the same
  payload so ``prices`` stores the raw prints the exchange actually produced;
  un-adjusted prices are quantized to whole VND (float32 noise — 73199.9984375
  → 73200) and volumes to whole shares.
* **No turnover field** — ``trading_value`` is approximated as
  ``close × volume`` (raw, post un-adjustment); Yahoo publishes no matched
  value, so this is a documented derivation, not the vendor's number.
* **Placeholder rows** — days with ``null`` OHLC or ``volume <= 0`` carry no
  trades (holiday carry-forwards / feed gaps) and are dropped rather than
  stored as fabricated bars; the completeness scorer reports them as missing.
* **``meta.fullExchangeName`` is wrong** for non-HOSE listings (reports
  ``HOSE`` for everything), so ``exchange`` comes from config; it is
  informational only — ``prices`` rows key on ``stock_id`` (reference data).

``period2`` extends to *today* so split events between a backfill window and
now are still in the payload; :meth:`HttpJsonProvider.fetch_eod` trims bars
back to the requested window afterwards.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import httpx

from src.data.providers.http_json import HttpJsonProvider, _substitute
from src.data.providers.rss import DEFAULT_USER_AGENT
from src.data.records import EODBar

_ONE = Decimal("1")
_QUOTE_KEYS = ("open", "high", "low", "close", "volume")


def _at(values: list[Any], index: int) -> Any:
    """Index into a parallel array, treating short/missing arrays as ``null``."""
    return values[index] if index < len(values) else None


def _split_ratios(payload: dict[str, Any]) -> list[tuple[int, Decimal]]:
    """``(split_timestamp, numerator/denominator)`` pairs, ascending by date."""
    events = payload.get("events") or {}
    ratios: list[tuple[int, Decimal]] = []
    for event in (events.get("splits") or {}).values():
        numerator = Decimal(str(event["numerator"]))
        denominator = Decimal(str(event["denominator"]))
        if denominator == 0:
            raise ValueError(f"split event with zero denominator: {event!r}")
        ratios.append((int(event["date"]), numerator / denominator))
    return sorted(ratios)


class YahooChartProvider(HttpJsonProvider):
    """EOD OHLCV from Yahoo's v8 chart endpoint for ``SYMBOL.VN`` tickers.

    Reuses :class:`HttpJsonProvider`'s retry/backoff transport and per-symbol
    fetch loop; only request construction and payload mapping are vendor-
    specific. Config keys (``endpoints.eod``): ``url`` (with ``{symbol}``),
    ``symbol_suffix``, ``interval``, ``user_agent``, ``exchange``,
    ``timezone_offset_hours``.
    """

    def _build_request(self, symbol: str, start: date, end: date) -> httpx.Request:
        cfg = self._cfg
        suffix = str(cfg.get("symbol_suffix", ".VN"))
        ticker = symbol.upper()
        if suffix and not ticker.endswith(suffix):
            ticker += suffix
        url = _substitute(str(cfg["url"]), {"{symbol}": ticker})
        tz = timezone(timedelta(hours=int(cfg.get("timezone_offset_hours", 7))))
        period1 = int(datetime(start.year, start.month, start.day, tzinfo=tz).timestamp())
        # Extend the upper bound to today: split events after a backfill window
        # still adjust the bars Yahoo serves, so they must be visible to un-adjust.
        upper = max(end, datetime.now(tz=UTC).astimezone(tz).date())
        period2 = int(datetime(upper.year, upper.month, upper.day, tzinfo=tz).timestamp())
        period2 += 86400  # exclusive: include every bar of the upper-bound day
        params = {
            "period1": str(period1),
            "period2": str(period2),
            "interval": str(cfg.get("interval", "1d")),
            "events": "split",
        }
        headers = {
            "User-Agent": str(cfg.get("user_agent", DEFAULT_USER_AGENT)),
            "Accept": "application/json",
        }
        if self._credential and self._auth == "bearer":
            headers["Authorization"] = f"Bearer {self._credential}"
        elif self._credential and self._auth == "query":
            params["apikey"] = self._credential
        headers.update(cfg.get("headers") or {})
        return httpx.Request("GET", url, params=params, headers=headers)

    def _map_rows(self, payload: Any) -> list[EODBar]:
        cfg = self._cfg
        chart = payload.get("chart") if isinstance(payload, dict) else None
        if not isinstance(chart, dict):
            raise ValueError(f"provider '{self.id}': malformed payload (missing 'chart')")
        error = chart.get("error")
        if error:
            raise ValueError(
                f"provider '{self.id}': {error.get('code')}: {error.get('description')}"
            )
        results = chart.get("result")
        if not results:
            raise ValueError(f"provider '{self.id}': empty chart result")

        node = results[0]
        meta = node.get("meta") or {}
        suffix = str(cfg.get("symbol_suffix", ".VN"))
        symbol = str(meta.get("symbol") or "").upper()
        if suffix and symbol.endswith(suffix):
            symbol = symbol[: -len(suffix)]
        if not symbol:
            raise ValueError(f"provider '{self.id}': payload has no symbol in meta")

        timestamps: list[int] = list(node.get("timestamp") or [])
        quote_block = (node.get("indicators") or {}).get("quote") or [{}]
        quote = quote_block[0] if quote_block else {}
        columns = {key: list(quote.get(key) or []) for key in _QUOTE_KEYS}
        splits = _split_ratios(node)

        tz = timezone(timedelta(hours=int(cfg.get("timezone_offset_hours", 7))))
        exchange = str(cfg.get("exchange", "HOSE")).upper()
        bars: list[EODBar] = []
        for index, timestamp in enumerate(timestamps):
            values = [_at(columns[key], index) for key in _QUOTE_KEYS]
            if any(value is None for value in values):
                continue  # null OHLC/volume — no honest bar to build
            volume_raw = int(values[4])
            if volume_raw <= 0:
                continue  # placeholder row (no trades): drop, don't fabricate

            ratio = _ONE
            for split_ts, split_ratio in splits:
                if split_ts > timestamp:
                    ratio *= split_ratio
            prices = [Decimal(str(value)) for value in values[:4]]
            volume = volume_raw
            if ratio != _ONE:
                # Un-adjust: Yahoo divided OHLC by the ratio and multiplied
                # volume; restore raw prints (quantize away float32 noise).
                prices = [
                    (value * ratio).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                    for value in prices
                ]
                volume = int(
                    (Decimal(volume_raw) / ratio).to_integral_value(rounding=ROUND_HALF_UP)
                )

            close = prices[3]
            bars.append(
                EODBar(
                    symbol=symbol,
                    exchange=exchange,
                    trade_date=datetime.fromtimestamp(timestamp, tz=tz).date(),
                    open=prices[0],
                    high=prices[1],
                    low=prices[2],
                    close=close,
                    volume=volume,
                    trading_value=(close * volume).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    ),
                )
            )
        return bars


__all__ = ["YahooChartProvider"]

