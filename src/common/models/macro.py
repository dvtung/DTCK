"""Macro data model (DATABASE_SCHEMA §8): macro_indicators hypertable."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Numeric, PrimaryKeyConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.common.models.base import Base


class MacroIndicator(Base):
    """§8.1 — Macro series (GDP, CPI, FX_USDVND, …). Hypertable on `period_date`."""

    __tablename__ = "macro_indicators"
    __table_args__ = (PrimaryKeyConstraint("indicator_code", "period_date"),)

    indicator_code: Mapped[str] = mapped_column(Text, nullable=False)
    period_date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    unit: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)


__all__ = ["MacroIndicator"]
