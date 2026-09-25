"""/api/v1/fundamentals (API_SPECIFICATION §2.3)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from apps.api.dependencies import MarketDep
from apps.api.routers.common import not_found
from apps.api.schemas import QualityOut

router = APIRouter(prefix="/api/v1/fundamentals", tags=["fundamentals"])


@router.get("/{symbol}/statements", response_model=None)
def statements(symbol: str, service: MarketDep) -> list[dict[str, Any]]:
    if service.get_stock(symbol.upper()) is None:
        raise not_found("stock", symbol)
    return service.get_statements(symbol.upper())


@router.get("/{symbol}/ratios", response_model=None)
def ratios(symbol: str, service: MarketDep) -> list[dict[str, Any]]:
    if service.get_stock(symbol.upper()) is None:
        raise not_found("stock", symbol)
    return service.get_ratios(symbol.upper())


@router.get("/{symbol}/quality", response_model=QualityOut)
def quality(symbol: str, service: MarketDep) -> dict[str, Any]:
    row = service.get_quality(symbol.upper())
    if not row:
        raise not_found("stock", symbol)
    return row
