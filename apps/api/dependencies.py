"""FastAPI dependencies (apps/api).

``get_market_service`` resolves the configured ``MarketSource``
(``MarketService`` in-memory fixture vs ``DbMarketService`` over TimescaleDB).
The default is the in-memory source so the API and its unit tests run with no
database; ``MARKET_DATA_SOURCE=db|auto`` switches the whole read path over
without touching a single router.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from apps.api.services.market_data import MarketService
from apps.api.services.market_source import MarketSource


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


# Idiomatic Annotated dependency for use in route signatures.
MarketDep = Annotated[MarketSource, Depends(get_market_service)]
