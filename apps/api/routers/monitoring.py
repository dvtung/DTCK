"""Monitoring endpoints for watchlist-scale alerting."""

from __future__ import annotations

from fastapi import APIRouter, Query

from apps.api.dependencies import get_market_service
from apps.api.services.rag_service import get_rag_service
from src.agents.monitoring.agent import MonitoringAgent
from src.agents.tools import ToolCatalog

router = APIRouter(prefix="/api/v1", tags=["monitoring"])


@router.get("/monitoring/alerts")
def alerts(
    symbols: str = Query(default="FPT,VCB", description="Comma-separated symbol list"),
) -> dict[str, object]:
    """Return monitoring alerts for the provided watchlist."""
    tools = ToolCatalog(get_market_service(), get_rag_service())
    agent = MonitoringAgent(tools)
    watchlist = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not watchlist:
        return {"alerts": []}
    return {"alerts": [a.model_dump(mode="json") for a in agent.monitor(watchlist)]}


__all__ = ["router"]
