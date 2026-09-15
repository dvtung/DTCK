"""/api/v1/news (API_SPECIFICATION §2.6)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from apps.api.dependencies import MarketDep
from apps.api.routers.common import page_of, paginate_params

router = APIRouter(prefix="/api/v1/news", tags=["news"])


@router.get("", response_model=dict)
def list_news(
    service: MarketDep,
    symbol: str | None = Query(default=None),
    source: str | None = Query(default=None),
    limit: int = Query(default=20),
    offset: int = Query(default=0),
) -> dict[str, Any]:
    rows = service.list_news()
    if symbol:
        rows = [r for r in rows if r.get("symbol") == symbol.upper()]
    if source:
        rows = [r for r in rows if r["source"] == source]
    limit, offset = paginate_params(limit, offset)
    return page_of(rows, len(rows), limit, offset)
