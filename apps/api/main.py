"""DTCK API application entry point.

FastAPI app exposing the /api/v1 groups (see docs/API_SPECIFICATION.md).
Route groups registered in include_router below.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.config import settings
from apps.api.routers import backtests, fundamentals, market, news, stocks, technical, valuation

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

for _router in (market.router, stocks.router, fundamentals.router, technical.router,
                valuation.router, news.router, backtests.router):
    app.include_router(_router)


@app.get("/healthz", tags=["system"])
def healthz() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "service": "api", "version": "0.1.0"}


@app.get("/readyz", tags=["system"])
def readyz() -> dict[str, str | dict[str, str]]:
    """Readiness probe — extend with DB/Qdrant connectivity checks."""
    return {"status": "ready", "dependencies": {"database": "pending", "qdrant": "pending"}}


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
