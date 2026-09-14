"""Market data model tables (DATABASE_SCHEMA §4/§6) — all TimescaleDB hypertables.

Each of these tables becomes a hypertable partitioned on its trade date in the
initial Alembic migration (see ``database/migrations/versions/``).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Computed,
    Date,
    ForeignKey,
    Numeric,
    PrimaryKeyConstraint,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.common.models.base import TIMESTAMPTZ, Base, TimestampMixin


class Price(TimestampMixin, Base):
    """§4.1 — Raw OHLCV per stock/day. Source data is never mutated."""

    __tablename__ = "prices"
    __table_args__ = (PrimaryKeyConstraint("stock_id", "trade_date"),)

    stock_id: Mapped[int] = mapped_column(
        ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    trading_value: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)


class AdjustedPrice(TimestampMixin, Base):
    """§4.2 — Split/dividend-adjusted prices, kept separate from raw ``prices``."""

    __tablename__ = "adjusted_prices"
    __table_args__ = (PrimaryKeyConstraint("stock_id", "trade_date"),)

    stock_id: Mapped[int] = mapped_column(
        ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    trading_value: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    adj_factor: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    adj_close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)


class IndexPrice(Base):
    """§4.3 — Index OHLCV (VNINDEX, VN30, …)."""

    __tablename__ = "index_prices"
    __table_args__ = (PrimaryKeyConstraint("index_code", "trade_date"),)

    index_code: Mapped[str] = mapped_column(Text, nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    trading_value: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)


class ForeignFlow(Base):
    """§4.4 — Daily foreign flows. ``foreign_net_value`` is a stored generated column."""

    __tablename__ = "foreign_flows"
    __table_args__ = (PrimaryKeyConstraint("stock_id", "trade_date"),)

    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    foreign_buy_value: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    foreign_sell_value: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    foreign_net_value: Mapped[Decimal] = mapped_column(
        Numeric(20, 2),
        Computed("foreign_buy_value - foreign_sell_value", persisted=True),
        nullable=False,
    )
    foreign_room_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)


class PropTradingFlow(Base):
    """§4.5 — Daily proprietary trading flows."""

    __tablename__ = "prop_trading_flows"
    __table_args__ = (PrimaryKeyConstraint("stock_id", "trade_date"),)

    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    prop_buy_value: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    prop_sell_value: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)


class ValuationDaily(Base):
    """§6.1 — Daily valuation snapshot (hypertable)."""

    __tablename__ = "valuation_daily"
    __table_args__ = (PrimaryKeyConstraint("stock_id", "trade_date"),)

    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    pe: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    forward_pe: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    pb: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    ev_ebitda: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    ev_sales: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    dividend_yield: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    peg: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    industry_pe_median: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)


__all__ = [
    "Price",
    "AdjustedPrice",
    "IndexPrice",
    "ForeignFlow",
    "PropTradingFlow",
    "ValuationDaily",
]
