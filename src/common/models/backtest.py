"""Backtesting models (DATABASE_SCHEMA §11): backtests, backtest_trades, backtest_metrics."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, Date, ForeignKey, Numeric, PrimaryKeyConstraint, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from src.common.models.base import Base, TimestampMixin


class Backtest(TimestampMixin, Base):
    """§11.1 — A run of a backtested strategy."""

    __tablename__ = "backtests"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True)
    strategy_name: Mapped[str] = mapped_column(Text, nullable=False)
    strategy_version: Mapped[str] = mapped_column(Text, nullable=False)
    universe: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    params: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    transaction_cost_bps: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    slippage_bps: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    run_type: Mapped[str] = mapped_column(Text, nullable=False)


class BacktestTrade(Base):
    """§11.2 — Individual trades produced by a backtest run."""

    __tablename__ = "backtest_trades"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    backtest_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("backtests.id", ondelete="CASCADE"), nullable=False
    )
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    exit_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    return_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)


class BacktestMetric(Base):
    """§11.3 — Performance metrics for a backtest (§16)."""

    __tablename__ = "backtest_metrics"
    __table_args__ = (PrimaryKeyConstraint("backtest_id", "metric_name"),)

    backtest_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("backtests.id", ondelete="CASCADE"), nullable=False
    )
    metric_name: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)


__all__ = ["Backtest", "BacktestTrade", "BacktestMetric"]
