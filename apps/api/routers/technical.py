"""/api/v1/technical (API_SPECIFICATION §2.4)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from apps.api.dependencies import MarketDep
from apps.api.routers.common import not_found

router = APIRouter(prefix="/api/v1/technical", tags=["technical"])


@router.get("/{symbol}/indicators", response_model=dict)
def indicators(symbol: str, service: MarketDep) -> dict[str, Any]:
    row = service.get_indicators(symbol.upper())
    if not row:
        raise not_found("stock", symbol)
    return row


@router.get("/{symbol}/features", response_model=None)
def features(symbol: str, service: MarketDep) -> dict[str, Any]:
    if service.get_stock(symbol.upper()) is None:
        raise not_found("stock", symbol)
    return {"symbol": symbol.upper(), "feature_version": "baseline_1.0", "rows": []}
