"""/api/v1/stocks — list, profile, prices, ranking (API_SPECIFICATION §2.2)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from apps.api.dependencies import MarketDep
from apps.api.routers.common import not_found, page_of, paginate_params
from apps.api.schemas import PriceRow, RankingOut, StockOut

router = APIRouter(prefix="/api/v1/stocks", tags=["stocks"])


@router.get("", response_model=dict)
def list_stocks(
    service: MarketDep,
    exchange: str | None = Query(default=None),
    sector: str | None = Query(default=None),
    vn30: bool | None = Query(default=None),
    limit: int = Query(default=20),
    offset: int = Query(default=0),
) -> dict[str, Any]:
    rows = service.list_stocks(exchange=exchange, sector=sector, vn30=vn30)
    limit, offset = paginate_params(limit, offset)
    return page_of(rows, len(rows), limit, offset)


@router.get("/ranked", response_model=list[RankingOut])
def ranked(service: MarketDep) -> list[dict[str, Any]]:
    return service.get_ranked()


@router.get("/{symbol}/prices", response_model=list[PriceRow])
def prices(symbol: str, service: MarketDep) -> list[dict[str, Any]]:
    rows = service.get_prices(symbol.upper())
    if not rows:
        raise not_found("stock", symbol)
    return rows


@router.get("/{symbol}/ranking", response_model=RankingOut)
def ranking(symbol: str, service: MarketDep) -> dict[str, Any]:
    row = service.get_ranking(symbol.upper())
    if not row:
        raise not_found("stock", symbol)
    return row


@router.get("/{symbol}", response_model=StockOut)
def stock(symbol: str, service: MarketDep) -> dict[str, Any]:
    meta = service.get_stock(symbol.upper())
    if not meta:
        raise not_found("stock", symbol)
    return meta
