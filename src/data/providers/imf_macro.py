"""IMF datamapper provider — official annual macro series for Vietnam (§8.1).

**Verified reachable from the dev host on 2026-10-03**
(``/external/datamapper/api/v1/{indicator}/VNM`` → 200 with real WEO data).
World Bank, GSO and SBV are not reachable from this host (timeout / no DNS /
HTML-only), so only the IMF half of the ``imf_worldbank`` entry is wired.

Honesty rule encoded here: the WEO vintage also publishes **projections** for
future years. Those are never stored — only completed calendar years are
returned (``max_year_offset``, default 1 → a year is written only once it has
finished). Forecast years are silently dropped rather than persisted as if they
were observations (§31).
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from src.data.providers.base import DataProvider
from src.data.providers.rss import DEFAULT_USER_AGENT
from src.data.records import MacroPoint

logger = logging.getLogger(__name__)

DEFAULT_IMF_ORIGIN = "https://www.imf.org/external/datamapper/api/v1"

#: Our indicator code → IMF code + unit (overridable via ``endpoints.macro``).
DEFAULT_MACRO_INDICATORS: dict[str, dict[str, str]] = {
    "GDP_GROWTH_PCT": {"code": "NGDP_RPCH", "unit": "percent"},
    "CPI_INFLATION_PCT": {"code": "PCPIPCH", "unit": "percent"},
}


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None


class ImfMacroProvider(DataProvider):
    """Annual macro series (IMF WEO datamapper) for a single country."""

    id: str = "imf_worldbank"
    SUPPORTED_DATASETS = frozenset({"macro"})

    def __init__(
        self,
        *,
        provider_id: str = "imf_worldbank",
        origin: str | None = None,
        country: str = "VNM",
        indicators: dict[str, dict[str, str]] | None = None,
        max_year_offset: int = 1,
        transport: httpx.BaseTransport | None = None,
        timeout_s: float = 30.0,
    ) -> None:
        self.id = provider_id
        self._origin = (origin or DEFAULT_IMF_ORIGIN).rstrip("/")
        self._country = country.upper()
        self._indicators = indicators or DEFAULT_MACRO_INDICATORS
        self._max_year_offset = max_year_offset
        self._transport = transport
        self._timeout_s = timeout_s

    # ------------------------------------------------------------- transport
    def _client(self) -> httpx.Client:
        return httpx.Client(
            transport=self._transport,
            timeout=self._timeout_s,
            headers={"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
        )

    def _get(self, imf_code: str) -> dict[str, Any]:
        url = f"{self._origin}/{imf_code}/{self._country}"
        with self._client() as client:
            response = client.get(url)
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(f"provider '{self.id}': malformed payload for {imf_code}")
        return payload

    # ---------------------------------------------------------------- macro
    def fetch_macro(
        self, indicators: list[str], *, start: date, end: date
    ) -> list[MacroPoint]:
        """Fetch configured annual series intersecting ``[start, end]``."""
        wanted = list(indicators) if indicators else list(self._indicators)
        unknown = [code for code in wanted if code not in self._indicators]
        if unknown:
            raise KeyError(
                f"provider '{self.id}': unknown indicators {unknown} "
                f"(configured: {sorted(self._indicators)})"
            )

        cutoff = datetime.now().date().year - self._max_year_offset
        rows: list[MacroPoint] = []
        for code in wanted:
            spec = self._indicators[code]
            imf_code = str(spec["code"])
            unit = str(spec.get("unit", "index"))
            payload = self._get(imf_code)
            series = ((payload.get("values") or {}).get(imf_code) or {}).get(self._country)
            if not isinstance(series, dict):
                raise ValueError(
                    f"provider '{self.id}': no series for {imf_code}/{self._country}"
                )
            for year_text, raw in series.items():
                try:
                    year = int(year_text)
                except (TypeError, ValueError):
                    continue
                if year < start.year or year > end.year:
                    continue
                if year > cutoff:
                    continue  # IMF projection — never stored as an observation
                value = _to_decimal(raw)
                if value is None:
                    continue
                rows.append(
                    MacroPoint(
                        indicator_code=code,
                        period_date=date(year, 12, 31),
                        value=value,
                        unit=unit,
                    )
                )
        return rows


__all__ = [
    "DEFAULT_IMF_ORIGIN",
    "DEFAULT_MACRO_INDICATORS",
    "ImfMacroProvider",
]
