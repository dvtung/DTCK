"""DTCK API application entry point.

FastAPI app exposing the /api/v1 groups (see docs/API_SPECIFICATION.md).
Route groups registered in include_router below.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.config import settings
from apps.api.routers import (
    agents,
    auth,
    backtests,
    fundamentals,
    market,
    monitoring,
    news,
    predictions,
    rag,
    stocks,
    technical,
    valuation,
)

app = FastAPI(
    title="DTCK AI Investment Platform",
    version="0.1.0",
    description=(
        "AI Investment Research & Decision Intelligence Platform "
        "(Vietnam Stock Market: HOSE / HNX / UPCOM)."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

for _router in (
    market.router,
    stocks.router,
    fundamentals.router,
    technical.router,
    valuation.router,
    news.router,
    backtests.router,
    rag.router,
    agents.router,
    auth.router,
    monitoring.router,
    predictions.router,
):
    app.include_router(_router)


@app.get("/healthz", tags=["system"])
def healthz() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "service": "api", "version": "0.1.0"}


@app.get("/readyz", tags=["system"])
def readyz() -> dict[str, str | dict[str, str]]:
    """Readiness probe — DB pending (KI-008), Qdrant + agents best-effort (KI-011/012)."""
    qdrant = "pending"
    try:
        from apps.api.services.rag_service import get_rag_service

        svc = get_rag_service()
        qdrant = "up" if svc.qdrant_available else "offline-index-ready"
    except Exception:  # noqa: BLE001
        qdrant = "offline-index-ready"
    agent_framework = "unavailable"
    try:
        from apps.api.services.agent_service import get_orchestrator

        orch = get_orchestrator()
        agent_framework = f"offline:{','.join(orch.registry.tasks())}"
    except Exception:  # noqa: BLE001
        agent_framework = "unavailable"
    return {"status": "ready",
            "dependencies": {"database": "pending", "qdrant": qdrant,
                             "agents": agent_framework}}


def run() -> None:
    """Console entry point: `dtck-api`."""
    import uvicorn

    uvicorn.run(
        "apps.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
