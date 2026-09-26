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


def _database_status() -> str:
    """Live DB status: ``connected`` · ``connected-no-prices`` · ``unreachable``.

    The API read path (``MARKET_DATA_SOURCE``, KI-008) only serves TimescaleDB
    once ``prices`` has rows, so "connected" and "connected but nothing to read
    yet" are reported separately instead of a hardcoded ``pending``.
    """
    try:
        from apps.api.db import database_is_ready

        if not database_is_ready(require_prices=False):
            return "unreachable"
        return "connected" if database_is_ready(require_prices=True) else "connected-no-prices"
    except Exception:  # noqa: BLE001 — a probe must never fail the endpoint
        return "unreachable"


def _qdrant_status() -> str:
    """``up`` when the Qdrant mirror answers, else the documented offline mode.

    ``offline-index-ready`` is a valid state, not an error: the RAG service keeps
    serving from the deterministic in-memory index (KI-011, ADR-001 fail-soft).
    """
    try:
        from apps.api.services.rag_service import get_rag_service

        return "up" if get_rag_service().qdrant_available else "offline-index-ready"
    except Exception:  # noqa: BLE001
        return "offline-index-ready"


def _agents_status() -> str:
    """``llm:<model>`` when the LLM tier is wired (T016), else the deterministic core.

    Reports the reasoning layer that would actually serve a run, so operators can
    tell a local Ollama deployment apart from the offline baseline.
    """
    try:
        from apps.api.services.agent_service import get_llm_client, get_orchestrator

        tasks = ",".join(get_orchestrator().registry.tasks())
        llm = get_llm_client()
        if llm is None:
            return f"offline:{tasks}"
        return f"llm:{getattr(llm, 'model', None) or settings.llm_model}"
    except Exception:  # noqa: BLE001
        return "unavailable"


def _market_source_status() -> str:
    """Configured read mode plus the service actually serving requests (KI-008)."""
    try:
        from apps.api.dependencies import get_market_service
        from apps.api.services.db_market import DbMarketService

        served = "db" if isinstance(get_market_service(), DbMarketService) else "memory"
        return f"{settings.market_data_source}->{served}"
    except Exception:  # noqa: BLE001
        return settings.market_data_source


@app.get("/readyz", tags=["system"])
def readyz() -> dict[str, str | dict[str, str]]:
    """Readiness probe — live status of every dependency (best-effort, never 5xx).

    * ``database`` — real connectivity + whether ``prices`` holds rows (KI-008);
    * ``qdrant`` — mirror reachable (``up``) or in-memory index (``offline-index-ready``, KI-011);
    * ``agents`` — reasoning layer: ``llm:<model>`` (T016) or the deterministic baseline;
    * ``market_source`` — ``<configured mode>-><service serving reads>``.
    """
    return {
        "status": "ready",
        "market_source": _market_source_status(),
        "dependencies": {
            "database": _database_status(),
            "qdrant": _qdrant_status(),
            "agents": _agents_status(),
        },
    }


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
