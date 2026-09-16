"""/api/v1/agents + /api/v1/analysis (§2.7/§2.11, spec §21/§31/§45).

Sync endpoints run the agent immediately and return the audited run; the
``/api/v1/analysis`` pair implements the documented async pattern (202 + poll).
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from apps.api.routers.common import not_found
from apps.api.schemas import (
    AgentRunAcceptedOut,
    AnalysisRequest,
    MonitorRequest,
    PortfolioRequest,
    ResearchRequest,
)
from apps.api.services.agent_service import get_orchestrator
from src.agents.orchestrator.agent import MODEL, TASK_ANALYZE, Orchestrator
from src.agents.schemas import AgentRunRecord, PortfolioPosition

AgentDep = Annotated[Orchestrator, Depends(get_orchestrator)]

router = APIRouter(tags=["agents"])

UNKNOWN_SYMBOL_MARKER = "unknown symbol"


def _run_error(run: AgentRunRecord) -> HTTPException:
    """Map a failed run onto the documented error envelope (§2.1 conventions)."""
    message = str((run.final_output or {}).get("error", "agent run failed"))
    body: dict[str, Any] = {
        "error": {
            "code": "not_found" if UNKNOWN_SYMBOL_MARKER in message else "agent_run_failed",
            "message": message,
            "details": str(run.agent_run_id),
        }
    }
    return HTTPException(
        status_code=404 if UNKNOWN_SYMBOL_MARKER in message else 422, detail=body
    )


def _ok(run: AgentRunRecord, key: str) -> dict[str, Any]:
    return {
        "agent_run_id": str(run.agent_run_id),
        "status": run.status,
        "attempts": run.attempts,
        "latency_ms": run.latency_ms,
        key: run.final_output,
    }


# --------------------------------------------------------------- registry
@router.get("/api/v1/agents", response_model=dict)
def list_agents(orch: AgentDep) -> dict[str, Any]:
    """Agent registry listing (§41): version, status, tools, output schema."""
    return {
        "agents": orch.registry.to_payload(),
        "tools": orch.tools.catalog,
        "model": MODEL,
    }


@router.get("/api/v1/agents/runs", response_model=dict)
def list_runs(
    orch: AgentDep,
    agent_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
) -> dict[str, Any]:
    """Run history (§31), newest first."""
    runs = orch.audit.list_runs(agent_id=agent_id, limit=limit)
    return {"items": [r.model_dump(mode="json") for r in runs], "total": len(runs)}


@router.get("/api/v1/agents/runs/{agent_run_id}", response_model=dict)
def get_run(agent_run_id: UUID, orch: AgentDep) -> dict[str, Any]:
    """Full audit record: plan, tool calls, latency, final output (§31)."""
    run = orch.audit.get(agent_run_id)
    if run is None:
        raise not_found("agent_run", str(agent_run_id))
    return run.model_dump(mode="json")


# ------------------------------------------------------------- sync runs
@router.post("/api/v1/agents/analyze", response_model=dict)
def analyze(payload: AnalysisRequest, orch: AgentDep) -> dict[str, Any]:
    """Analysis Agent (§20.2) → structured ``InvestmentAnalysis`` (§23)."""
    run = orch.analyze(payload.symbol, user_request=payload.user_request)
    if run.status != "succeeded":
        raise _run_error(run)
    return _ok(run, "analysis")


@router.post("/api/v1/agents/research", response_model=dict)
def research(payload: ResearchRequest, orch: AgentDep) -> dict[str, Any]:
    """Research Agent (§20.1) → profile facts, news and §19 evidence."""
    run = orch.research(
        payload.symbol, query=payload.query or "", user_request=payload.user_request
    )
    if run.status != "succeeded":
        raise _run_error(run)
    return _ok(run, "brief")


@router.post("/api/v1/agents/monitor", response_model=dict)
def monitor(payload: MonitorRequest, orch: AgentDep) -> dict[str, Any]:
    """Monitoring Agent (§20.3) → §42 alerts for a watchlist."""
    run = orch.monitor(
        payload.symbols,
        previous_signals=payload.previous_signals,
        user_request=payload.user_request,
    )
    if run.status != "succeeded":
        raise _run_error(run)
    return _ok(run, "report")


@router.post("/api/v1/agents/portfolio", response_model=dict)
def portfolio(payload: PortfolioRequest, orch: AgentDep) -> dict[str, Any]:
    """Portfolio Agent (§20.4/§27) → concentration/exposure/risk snapshot."""
    positions = [PortfolioPosition(**p.model_dump()) for p in payload.positions]
    run = orch.portfolio(
        positions,
        risk_budget_annual_vol=payload.risk_budget_annual_vol,
        user_request=payload.user_request,
    )
    if run.status != "succeeded":
        raise _run_error(run)
    return _ok(run, "snapshot")


# --------------------------------------------------------- async pattern
@router.post(
    "/api/v1/analysis/request",
    response_model=AgentRunAcceptedOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_analysis(
    payload: AnalysisRequest, background: BackgroundTasks, orch: AgentDep
) -> dict[str, Any]:
    """Enqueue an analysis run; poll ``/api/v1/analysis/request/{id}`` (§2.7/§45)."""
    run = orch.submit(
        TASK_ANALYZE, {"symbol": payload.symbol}, user_request=payload.user_request
    )
    background.add_task(orch.execute_deferred, run.agent_run_id)
    return {"agent_run_id": run.agent_run_id, "status": run.status}


@router.get("/api/v1/analysis/request/{agent_run_id}", response_model=dict)
def analysis_status(agent_run_id: UUID, orch: AgentDep) -> dict[str, Any]:
    """Status + structured result of a queued analysis run (§2.7/§45)."""
    run = orch.audit.get(agent_run_id)
    if run is None:
        raise not_found("agent_run", str(agent_run_id))
    return {
        "agent_run_id": str(run.agent_run_id),
        "status": run.status,
        "attempts": run.attempts,
        "latency_ms": run.latency_ms,
        "analysis": run.final_output,
    }


@router.get("/api/v1/analysis/{symbol}/latest", response_model=dict)
def latest_analysis(symbol: str, orch: AgentDep) -> dict[str, Any]:
    """Latest successful stored analysis for a symbol (§2.7)."""
    run = orch.audit.latest_analysis(symbol)
    if run is None:
        raise not_found("analysis", symbol)
    return {
        "agent_run_id": str(run.agent_run_id),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "confidence": (run.final_output or {}).get("confidence"),
        "analysis": run.final_output,
    }


__all__ = ["router"]
