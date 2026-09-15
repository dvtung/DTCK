"""/api/v1/fundamentals (API_SPECIFICATION §2.3)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from apps.api.dependencies import MarketDep
from apps.api.routers.common import not_found
from apps.api.schemas import QualityOut

router = APIRouter(prefix="/api/v1/fundamentals", tags=["fundamentals"])

# Representative statement skeleton as sample rows.
_SAMPLE_STATEMENTS: list[dict[str, Any]] = [
    {"period_end": "2026-06-30", "statement_type": "income", "currency": "VND",
     "items": {"revenue": 2.4e12, "net_income": 4.1e11}},
    {"period_end": "2026-03-31", "statement_type": "income", "currency": "VND",
     "items": {"revenue": 2.1e12, "net_income": 3.7e11}},
]


@router.get("/{symbol}/statements", response_model=None)
def statements(symbol: str, service: MarketDep) -> list[dict[str, Any]]:
    if service.get_stock(symbol.upper()) is None:
        raise not_found("stock", symbol)
    return _SAMPLE_STATEMENTS


@router.get("/{symbol}/ratios", response_model=None)
def ratios(symbol: str, service: MarketDep) -> list[dict[str, Any]]:
    if service.get_stock(symbol.upper()) is None:
        raise not_found("stock", symbol)
    return [
        {"period_end": "2026-06-30", "name": "roe", "value": 0.21},
        {"period_end": "2026-06-30", "name": "debt_to_equity", "value": 0.42},
    ]


@router.get("/{symbol}/quality", response_model=QualityOut)
def quality(symbol: str, service: MarketDep) -> dict[str, Any]:
    row = service.get_quality(symbol.upper())
    if not row:
        raise not_found("stock", symbol)
    return row
