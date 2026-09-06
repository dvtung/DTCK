"""Alembic environment — Phase-0 scaffold.

Target metadata binding (tables from src) is wired in Phase 1 (T003) once the
SQLAlchemy models for the DATABASE_SCHEMA have been written.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Import models' metadata here once models exist (Phase 1):
# from src.<domain>.models import Base  # noqa: F401
target_metadata = None  # set to Base.metadata in T003

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Prefer DATABASE_URL env var; fall back to alembic.ini url.
database_url = os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
