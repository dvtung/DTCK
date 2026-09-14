"""Fundamental data models (DATABASE_SCHEMA §5): financial_statements, financial_ratios."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    ForeignKey,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.common.models.base import TIMESTAMPTZ, Base, TimestampMixin


class FinancialStatement(TimestampMixin, Base):
    """§5.1 — Bitemporal financial statement line items (restatement-aware).

    ``valid_from``/``valid_to`` encode business validity so the backtester can
    query "as-of" a date without look-ahead bias (``valid_from <= as_of <
    COALESCE(valid_to, 'infinity')``).
    """

    __tablename__ = "financial_statements"
    __table_args__ = (
        UniqueConstraint(
            "stock_id",
            "period_type",
            "fiscal_year",
            "fiscal_period",
            "statement_type",
            "line_item",
            "valid_from",
            name="uq_fin_statements_key",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    period_type: Mapped[str] = mapped_column(Text, nullable=False)  # QUARTER | YEAR
    fiscal_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    fiscal_period: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 1-4 or 0
    statement_type: Mapped[str] = mapped_column(Text, nullable=False)  # INCOME|BALANCE|CASHFLOW
    line_item: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(24, 4), nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default="VND")
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)


class FinancialRatio(TimestampMixin, Base):
    """§5.2 — Precomputed deterministic ratios (never LLM-generated)."""

    __tablename__ = "financial_ratios"
    __table_args__ = (
        UniqueConstraint(
            "stock_id",
            "period_type",
            "fiscal_year",
            "fiscal_period",
            "ratio_name",
            "calc_version",
            name="uq_fin_ratios_key",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    period_type: Mapped[str] = mapped_column(Text, nullable=False)
    fiscal_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    fiscal_period: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    ratio_name: Mapped[str] = mapped_column(Text, nullable=False)  # ROE, ROA, EPS, ...
    value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    calc_version: Mapped[str] = mapped_column(Text, nullable=False)


__all__ = ["FinancialStatement", "FinancialRatio"]
