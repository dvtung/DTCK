"""Quant engine output models (DATABASE_SCHEMA §9): features, factor_scores, signals, regimes."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    ForeignKey,
    Numeric,
    PrimaryKeyConstraint,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.common.models.base import TIMESTAMPTZ, Base, TimestampMixin


class Feature(TimestampMixin, Base):
    """§9.1 — Generic feature store (hypertable). Versioned per calculation run."""

    __tablename__ = "features"
    __table_args__ = (
        PrimaryKeyConstraint("stock_id", "trade_date", "feature_name", "feature_version"),
    )

    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    feature_name: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    feature_version: Mapped[str] = mapped_column(Text, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)


class FactorScore(TimestampMixin, Base):
    """§9.2 — Daily factor scores + overall composite (hypertable)."""

    __tablename__ = "factor_scores"
    __table_args__ = (PrimaryKeyConstraint("stock_id", "trade_date", "scoring_version"),)

    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    technical_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    fundamental_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    valuation_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    momentum_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    quality_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    risk_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    overall_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    scoring_version: Mapped[str] = mapped_column(Text, nullable=False)
    market_regime: Mapped[str | None] = mapped_column(Text, nullable=True)


class Signal(TimestampMixin, Base):
    """§9.3 — Detected signals (hypertable).

    TimescaleDB requires the partitioning column in every unique index, so the
    primary key is composite ``(id, trade_date)`` even though ``id`` is the
    surrogate row identifier.
    """

    __tablename__ = "signals"
    __table_args__ = (PrimaryKeyConstraint("id", "trade_date"),)

    id: Mapped[int] = mapped_column(BigInteger, autoincrement=True, nullable=False)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    signal_type: Mapped[str] = mapped_column(Text, nullable=False)
    signal_value: Mapped[str] = mapped_column(Text, nullable=False)
    strength: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    horizon: Mapped[str] = mapped_column(Text, nullable=False)
    generated_by: Mapped[str] = mapped_column(Text, nullable=False)


class MarketRegime(Base):
    """§9.4 — Detected market regime per day (hypertable)."""

    __tablename__ = "market_regimes"
    __table_args__ = (PrimaryKeyConstraint("trade_date"),)

    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    regime: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    inputs: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)


__all__ = ["Feature", "FactorScore", "Signal", "MarketRegime"]
