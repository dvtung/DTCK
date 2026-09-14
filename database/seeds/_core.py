"""Shared helpers for reference-data seeds."""

from __future__ import annotations

import os

from sqlalchemy import Engine, create_engine


def get_engine() -> Engine:
    """Return a SQLAlchemy engine for the DTCK database (from DATABASE_URL)."""
    url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://dtck:change_me@localhost:5432/dtck",
    )
    return create_engine(url, pool_pre_ping=True)
