"""FastAPI dependencies (apps/api).

``get_market_service`` resolves the configured ``MarketSource``
(``MarketService`` in-memory fixture vs ``DbMarketService`` over TimescaleDB).
The default is the in-memory source so the API and its unit tests run with no
database; ``MARKET_DATA_SOURCE=db|auto`` switches the whole read path over
without touching a single router.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends

from apps.api.services.market_data import MarketService
from apps.api.services.market_source import MarketSource

if TYPE_CHECKING:
    from apps.api.services.strategy_service import StrategySource


@lru_cache(maxsize=1)
def get_market_service() -> MarketSource:
    """Provide the configured market-data source (cached process-wide)."""
    from apps.api.config import settings
    from apps.api.db import database_is_ready
    from apps.api.services.db_market import DbMarketService

    mode = (settings.market_data_source or "memory").strip().lower()
    if mode == "db":
        return DbMarketService()
    if mode == "auto" and database_is_ready(require_prices=True):
        return DbMarketService()
    return MarketService()


@lru_cache(maxsize=1)
def get_strategy_service() -> StrategySource:
    """Provide the strategy-scoring reader (DB when available, else empty)."""
    from apps.api.config import settings
    from apps.api.db import database_is_ready
    from apps.api.services.strategy_service import (
        DbStrategyService,
        NullStrategyService,
    )

    mode = (settings.market_data_source or "memory").strip().lower()
    if mode == "db" or (mode == "auto" and database_is_ready()):
        return DbStrategyService()
    return NullStrategyService()


# Idiomatic Annotated dependency for use in route signatures.
MarketDep = Annotated[MarketSource, Depends(get_market_service)]
StrategyDep = Annotated["StrategySource", Depends(get_strategy_service)]
