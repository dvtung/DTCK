"""Shared SQLAlchemy declarative base and common table scaffolding.

STEP 2 (DATABASE DESIGN) implementation — the single source of truth for the
schema defined in ``docs/DATABASE_SCHEMA.md``. Alembic migrations create every
table by reflecting this metadata (``src.common.models.Base.metadata``).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, MetaData, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Consistent constraint/index naming so Alembic can manage them deterministically.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base shared by every domain model."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# PostgreSQL ``timestamptz`` (timezone-aware UTC timestamps).
TIMESTAMPTZ = TIMESTAMP(timezone=True)


class TimestampMixin:
    """Adds ``created_at`` timestamptz to the table (schema principle #4)."""

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=func.now(), nullable=False
    )


class AuditMixin(TimestampMixin):
    """``TimestampMixin`` plus an ``updated_at`` column for mutable rows."""

    updated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMPTZ, server_default=func.now(), onupdate=func.now(), nullable=True
    )


__all__ = [
    "Base",
    "NAMING_CONVENTION",
    "TIMESTAMPTZ",
    "TimestampMixin",
    "AuditMixin",
    "BigInteger",
    "JSONB",
    "MetaData",
    "func",
    "datetime",
    "mapped_column",
]
