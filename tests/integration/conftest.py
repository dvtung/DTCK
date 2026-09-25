"""Fixtures for database-backed integration tests (W1+).

These tests run against the real PostgreSQL/TimescaleDB instance configured by
``DATABASE_URL``. They **skip** when that instance is unreachable or has not been
migrated, so ``pytest`` still succeeds on a fresh clone with no services up.

Documented runner (see ``helper/deployment.md``):

    docker compose up -d db
    docker compose exec api alembic upgrade head
    pytest tests/integration -q
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.db import get_engine, session_factory


def _database_available() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM stocks LIMIT 1"))
        return True
    except Exception:  # noqa: BLE001 — unreachable/un-migrated DB means "skip"
        return False


@pytest.fixture(scope="session")
def db_ready() -> None:
    if not _database_available():
        pytest.skip("database unreachable or not migrated — run alembic upgrade head")


@pytest.fixture
def session(db_ready: None) -> Iterator[Session]:
    """Read/write session for fixtures; always closed on teardown."""
    sess = session_factory()
    try:
        yield sess
    finally:
        sess.close()


@pytest.fixture
def db_service(db_ready: None):
    """A ``DbMarketService`` bound to the configured database."""
    from apps.api.services.db_market import DbMarketService

    return DbMarketService()
