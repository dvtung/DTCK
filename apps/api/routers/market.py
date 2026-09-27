"""/api/v1/market — index snapshots, regime, breadth (API_SPECIFICATION §2.1)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from apps.api.dependencies import MarketDep
from apps.api.routers.common import not_found
from apps.api.schemas import BreadthOut, IndexPriceOut, MoversOut, RegimeOut

router = APIRouter(prefix="/api/v1/market", tags=["market"])


@router.get("/indices", response_model=list[IndexPriceOut])
def list_indices(service: MarketDep) -> list[dict[str, Any]]:
    return service.list_indices()


@router.get("/indices/{code}", response_model=IndexPriceOut)
def get_index(code: str, service: MarketDep) -> dict[str, Any]:
    row = service.get_index(code.upper())
    if not row:
        raise not_found("index", code)
    return row


@router.get("/indices/{code}/prices", response_model=list[IndexPriceOut])
def get_index_prices(code: str, service: MarketDep) -> list[dict[str, Any]]:
    rows = service.get_index_prices(code.upper())
    if rows is None:
        raise not_found("index", code)
    return rows


@router.get("/regime", response_model=RegimeOut)
def get_regime(service: MarketDep) -> dict[str, Any]:
    return service.get_regime()


@router.get("/breadth", response_model=BreadthOut)
def get_breadth(service: MarketDep) -> dict[str, Any]:
    return service.get_breadth()


@router.get("/movers", response_model=MoversOut)
def get_movers(
    service: MarketDep,
    universe: str = "VN100",
    limit: int = 10,
) -> dict[str, Any]:
    return service.get_movers(universe=universe, limit=limit)
