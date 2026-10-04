"""Data provider abstraction (T004).

A provider turns a vendor payload into the provider-agnostic records in
``src.data.records``. Everything downstream (validators, normalizers, pipeline,
quality) is vendor-agnostic, so swapping a vendor never touches pipeline code
(mirrors the LLM abstraction ADR-005, and the T002 design in
``docs/DATA_SOURCES.md`` §3).
"""

from __future__ import annotations

from abc import ABC
from datetime import date, datetime

from src.data.records import EODBar, EventRow, FinancialRow, IndexBar, MacroPoint, NewsItem


class DataProvider(ABC):  # noqa: B024 — interface defined by methods, not @abstractmethod
    """Common provider contract.

    A provider declares the datasets it can serve via ``SUPPORTED_DATASETS``;
    collectors check ``supports()`` and fall back to the next provider otherwise.
    Subclasses override the ``fetch_*`` methods they support; the defaults raise
    ``NotImplementedError`` so unsupported operations fail loudly.
    """

    id: str = "unset"
    SUPPORTED_DATASETS: frozenset[str] = frozenset()

    def supports(self, dataset: str) -> bool:
        """Report whether this provider can serve ``dataset``."""
        return dataset in self.SUPPORTED_DATASETS

    def fetch_eod(self, symbols: list[str], start: date, end: date) -> list[EODBar]:
        """Fetch end-of-day OHLCV bars for ``symbols`` in ``[start, end]``."""
        raise NotImplementedError(f"provider '{self.id}' does not implement prices")

    def fetch_index(self, index_codes: list[str], start: date, end: date) -> list[IndexBar]:
        """Fetch index OHLCV bars for ``index_codes`` in ``[start, end]``."""
        raise NotImplementedError(f"provider '{self.id}' does not implement index_prices")

    def fetch_news(self, since: datetime) -> list[NewsItem]:
        """Fetch news items published after ``since``."""
        raise NotImplementedError(f"provider '{self.id}' does not implement news")

    def fetch_financials(
        self, symbols: list[str], *, period_types: tuple[str, ...]
    ) -> list[FinancialRow]:
        """Fetch financial-statement line items for ``symbols`` (§5.1)."""
        raise NotImplementedError(f"provider '{self.id}' does not implement financials")

    def fetch_events(self, symbols: list[str], *, since: date) -> list[EventRow]:
        """Fetch corporate events on/after ``since`` (§7.1)."""
        raise NotImplementedError(f"provider '{self.id}' does not implement events")

    def fetch_macro(self, indicators: list[str], *, start: date, end: date) -> list[MacroPoint]:
        """Fetch macro series observations in ``[start, end]`` (§8.1)."""
        raise NotImplementedError(f"provider '{self.id}' does not implement macro")
