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

from collections.abc import Callable, Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

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


@pytest.fixture
def isolated_session_factory(db_ready: None) -> Iterator[Callable[[], Session]]:
    """Service session factory whose writes are rolled back at teardown.

    Integration tests run against the developer's ``DATABASE_URL`` — the same
    database the API and worker use.  Writes issued through the app's global
    ``session_factory`` therefore survive the run and can destroy real
    configuration (T018 regression: an unconditional
    ``DELETE FROM email_smtp_configs`` inside a test wiped the configured Gmail
    account).  This fixture binds services to a single connection inside an
    outer transaction that is **always rolled back**, so the suite still
    exercises real SQL while leaving the shared database untouched.
    """
    connection = get_engine().connect()
    trans = connection.begin()
    maker = sessionmaker(bind=connection, autoflush=False, expire_on_commit=False)
    try:
        yield maker
    finally:
        trans.rollback()
        connection.close()
