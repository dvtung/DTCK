"""/api/v1/valuation (API_SPECIFICATION §2.5)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from apps.api.dependencies import MarketDep
from apps.api.routers.common import not_found
from apps.api.schemas import ValuationSummaryOut

router = APIRouter(prefix="/api/v1/valuation", tags=["valuation"])


@router.get("/{symbol}/summary", response_model=ValuationSummaryOut)
def summary(symbol: str, service: MarketDep) -> dict[str, Any]:
    row = service.get_valuation_summary(symbol.upper())
    if not row:
        raise not_found("stock", symbol)
    return row


@router.get("/{symbol}/history", response_model=None)
def history(symbol: str, service: MarketDep) -> list[dict[str, Any]]:
    if service.get_stock(symbol.upper()) is None:
        raise not_found("stock", symbol)
    return [
        {"trade_date": "2026-08-01", "pe": 12.0, "pb": 2.0},
        {"trade_date": "2026-08-08", "pe": 12.4, "pb": 2.05},
    ]
