"""Portfolio models (DATABASE_SCHEMA §14): portfolios, positions, snapshots."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Date,
    ForeignKey,
    Numeric,
    PrimaryKeyConstraint,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from src.common.models.base import TIMESTAMPTZ, Base


class Portfolio(Base):
    """§14.1 — A user-owned portfolio."""

    __tablename__ = "portfolios"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)


class PortfolioPosition(Base):
    """§14.2 — Positions within a portfolio."""

    __tablename__ = "portfolio_positions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
    )
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)


class PortfolioSnapshot(Base):
    """§14.3 — Daily portfolio valuation snapshots (hypertable on snapshot_date)."""

    __tablename__ = "portfolio_snapshots"
    __table_args__ = (PrimaryKeyConstraint("portfolio_id", "snapshot_date"),)

    portfolio_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_value: Mapped[Decimal] = mapped_column(Numeric(24, 4), nullable=False)
    expected_return: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    volatility: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    beta: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    max_drawdown: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    sector_exposure: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    concentration: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)


__all__ = ["Portfolio", "PortfolioPosition", "PortfolioSnapshot"]
