"""FastAPI dependencies (apps/api)."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from apps.api.services.market_data import MarketService


@lru_cache
def get_market_service() -> MarketService:
    """Provide the deterministic in-memory market service (MVP-1 read API)."""
    return MarketService()


# Idiomatic Annotated dependency for use in route signatures.
MarketDep = Annotated[MarketService, Depends(get_market_service)]
