"""Database engine/session plumbing for the API read path (W1).

The API read path is DB-backed when ``MARKET_DATA_SOURCE`` selects it
(``apps/api/dependencies.py``); this module owns the connection lifecycle so the
routers and services never create engines themselves.

Nothing here writes: the API is a read-only consumer of data the worker ingests
(see ``src/data/pipelines.py``). Queries use ``pool_pre_ping`` so a container
restart (or a paused database) does not hand out dead connections.
"""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Process-wide engine built from ``settings.database_url`` (cached once)."""
    from apps.api.config import settings

    return create_engine(settings.database_url, pool_pre_ping=True, future=True)


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def session_factory() -> Session:
    """Open a new read session (the caller closes it; ``DbMarketService`` does)."""
    return _session_factory()()


def database_is_ready(*, require_prices: bool = True) -> bool:
    """True when the database answers and (optionally) already holds price rows.

    Used by the ``auto`` market-data source so a fresh clone — socket available
    but schema/data absent — falls back to the deterministic in-memory service
    instead of serving empty payloads.
    """
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
            if not require_prices:
                return True
            return conn.execute(text("SELECT 1 FROM prices LIMIT 1")).first() is not None
    except Exception:  # noqa: BLE001 — any failure means "not ready" by design
        return False


__all__ = ["get_engine", "session_factory", "database_is_ready"]
