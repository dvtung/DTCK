"""Machine-learning models (DATABASE_SCHEMA §10): registry, predictions, evaluations."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.common.models.base import TIMESTAMPTZ, Base, TimestampMixin


class ModelRegistry(TimestampMixin, Base):
    """§10.1 — ML model governance registry (§40)."""

    __tablename__ = "model_registry"
    __table_args__ = (PrimaryKeyConstraint("model_id", "version"),)

    model_id: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    training_data_version: Mapped[str] = mapped_column(Text, nullable=False)
    feature_version: Mapped[str] = mapped_column(Text, nullable=False)
    training_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    training_period_end: Mapped[date] = mapped_column(Date, nullable=False)
    validation_period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    validation_period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    test_period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    test_period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    metrics: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    parameters: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    owner: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="EXPERIMENTAL"
    )


class Prediction(TimestampMixin, Base):
    """§10.2 — ML predictions.

    NOTE (design decision): declared a hypertable in DATABASE_SCHEMA §17, but
    created as a **regular table** here because TimescaleDB requires the
    partitioning column in every unique index, and ``prediction_evaluations``
    holds a foreign key on ``predictions.id``. See memory-bank/decisions.md.
    """

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    model_id: Mapped[str] = mapped_column(Text, nullable=False)
    model_version: Mapped[str] = mapped_column(Text, nullable=False)
    feature_version: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[str] = mapped_column(Text, nullable=False)
    predicted_value: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)


class PredictionEvaluation(Base):
    """§10.3 — Outcome tracking for predictions (§26)."""

    __tablename__ = "prediction_evaluations"
    __table_args__ = (PrimaryKeyConstraint("prediction_id"),)

    prediction_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("predictions.id", ondelete="CASCADE"), nullable=False
    )
    actual_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    error: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    hit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


__all__ = ["ModelRegistry", "Prediction", "PredictionEvaluation"]
