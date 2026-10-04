"""/api/v1/strategy — chấm điểm 3 chiến lược + gợi ý (GĐ 6).

Read-only. Every payload carries the §3 disclaimer; ``grade`` may be ``null``
when the overall score is missing (never a fabricated letter).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from apps.api.dependencies import StrategyDep
from apps.api.routers.common import not_found, page_of, paginate_params

router = APIRouter(prefix="/api/v1/strategy", tags=["strategy"])


@router.get("/rankings", response_model=dict)
def rankings(
    service: StrategyDep,
    strategy: str = Query(default="mid", description="short | mid | long"),
    universe: str | None = Query(default=None, description="vn30 | vn100"),
    limit: int = Query(default=20),
    offset: int = Query(default=0),
) -> dict[str, Any]:
    """Ranked scores for one profile on the latest scored session."""
    try:
        rows = service.rankings(strategy, universe=universe)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    limit, offset = paginate_params(limit, offset)
    return page_of(rows, len(rows), limit, offset)


@router.get("/{symbol}", response_model=dict)
def symbol_scores(symbol: str, service: StrategyDep) -> dict[str, Any]:
    """All three profiles (grade, levels, reasons, disclaimer) for one symbol."""
    row = service.symbol_view(symbol.upper())
    if not row:
        raise not_found("strategy score", symbol)
    return row


@router.get("/{symbol}/history", response_model=dict)
def symbol_history(
    symbol: str,
    service: StrategyDep,
    strategy: str = Query(default="mid"),
    limit: int = Query(default=60),
) -> dict[str, Any]:
    """Score/grade history for one symbol and profile (oldest first)."""
    try:
        rows = service.history(symbol.upper(), strategy, limit=max(1, min(limit, 500)))
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"symbol": symbol.upper(), "strategy": strategy, "items": rows}
