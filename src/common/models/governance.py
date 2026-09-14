"""Governance, audit and data-quality models (DATABASE_SCHEMA §15)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.common.models.base import TIMESTAMPTZ, Base


class AuditLog(Base):
    """§15.1 — Append-only audit trail (§31/§41). Application roles get no
    UPDATE/DELETE grants on this table.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)


class DataQualityScore(Base):
    """§15.2 — Data quality framework scores per dataset/stock/as-of (§39)."""

    __tablename__ = "data_quality_scores"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    dataset: Mapped[str] = mapped_column(Text, nullable=False)
    stock_id: Mapped[int | None] = mapped_column(
        ForeignKey("stocks.id", ondelete="SET NULL"), nullable=True
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    completeness: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    accuracy: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    consistency: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    freshness: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    uniqueness: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    validity: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    overall_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    below_threshold: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


__all__ = ["AuditLog", "DataQualityScore"]
