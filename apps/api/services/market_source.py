"""The market-data source contract consumed by every ``/api/v1`` router (W1).

Two implementations satisfy it:

* ``apps/api/services/market_data.MarketService`` — deterministic in-memory
  fixture used for tests, demos and DB-less runs (KI-008 fallback).
* ``apps/api/services/db_market.DbMarketService`` — TimescaleDB-backed read
  path that serves what the ingestion pipeline actually wrote.

Routers depend on this protocol, never on a concrete class (``MarketDep``), so
swapping the source is a configuration change.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MarketSource(Protocol):
    """Read-only market-data surface shared by the in-memory and DB sources.

    ``runtime_checkable`` so the wiring can assert conformance at runtime (the
    check is method-presence only — signatures are enforced statically by mypy).
    """

    # ------------------------------------------------------------------ market
    def list_indices(self) -> list[dict[str, Any]]:
        """Latest snapshot per index code."""
        ...

    def get_index(self, code: str) -> dict[str, Any] | None:
        """Latest snapshot for one index code, or ``None`` when unknown."""
        ...

    def get_regime(self) -> dict[str, Any]:
        """Current market regime snapshot."""
        ...

    def get_breadth(self) -> dict[str, Any]:
        """Advancers/decliners/unchanged counts for the latest trade date."""
        ...

    # ------------------------------------------------------------------ stocks
    def list_stocks(
        self, exchange: str | None, sector: str | None, vn30: bool | None
    ) -> list[dict[str, Any]]:
        """Reference universe filtered by exchange/sector/VN30 membership."""
        ...

    def get_stock(self, symbol: str) -> dict[str, Any] | None:
        """Reference profile for one symbol, or ``None`` when unknown."""
        ...

    def get_prices(self, symbol: str) -> list[dict[str, Any]] | None:
        """EOD OHLCV series for one symbol (oldest first), or ``None``."""
        ...

    # ----------------------------------------------------------------- ranking
    def get_ranking(self, symbol: str) -> dict[str, Any] | None:
        """Ranking row for one symbol, or ``None`` when it is unranked."""
        ...

    def get_ranked(self) -> list[dict[str, Any]]:
        """Full ranked universe, best first."""
        ...

    # ------------------------------------------------- fundamentals/technical
    def get_indicators(self, symbol: str) -> dict[str, Any] | None:
        """Technical indicator snapshot for one symbol."""
        ...

    def get_features(self, symbol: str) -> dict[str, Any]:
        """Stored feature rows for one symbol (empty when none are persisted)."""
        ...

    def get_valuation_summary(self, symbol: str) -> dict[str, Any] | None:
        """Latest valuation snapshot for one symbol."""
        ...

    def get_valuation_history(self, symbol: str) -> list[dict[str, Any]]:
        """Valuation history (newest first) for one symbol."""
        ...

    def get_quality(self, symbol: str) -> dict[str, Any] | None:
        """Latest data-quality score for one symbol."""
        ...

    def get_statements(self, symbol: str) -> list[dict[str, Any]]:
        """Financial statements for one symbol (newest first)."""
        ...

    def get_ratios(self, symbol: str) -> list[dict[str, Any]]:
        """Financial ratios for one symbol (newest first)."""
        ...

    # -------------------------------------------------------------------- news
    def list_news(self) -> list[dict[str, Any]]:
        """News items, newest first."""
        ...

    # --------------------------------------------------------------- backtests
    def get_backtest(self, bt_id: str) -> dict[str, Any] | None:
        """One backtest run, or ``None`` when unknown."""
        ...

    def list_backtests(self) -> list[dict[str, Any]]:
        """All backtest runs."""
        ...

    def get_backtest_metrics(self, bt_id: str) -> list[dict[str, Any]]:
        """Metrics for one run (empty when unknown or unscored)."""
        ...

    def get_backtest_trades(self, bt_id: str) -> list[dict[str, Any]]:
        """Trades for one run (empty when unknown or not persisted)."""
        ...


__all__ = ["MarketSource"]
