"""Strategy scoring output models: multi-profile scores + recommendations.

New tables (migration ``0005_strategy_scoring``) — deliberately kept separate
from ``factor_scores`` so the existing six-dimension ranking (§12) and
``/api/v1/stocks/ranked`` stay untouched (T020-era data preserved).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, PrimaryKeyConstraint, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.common.models.base import Base, TimestampMixin


class StrategyScore(TimestampMixin, Base):
    """One stock's multi-group score for one strategy profile on a trade date.

    Group columns mirror the keys in ``configs/strategy_weights.yaml``
    (technical/moneyflow/growth/quality/valuation/macro/governance). Missing
    groups are NULL — never invented (spec §3 honesty rule). Hypertable on
    ``trade_date`` (migration 0005).
    """

    __tablename__ = "strategy_scores"
    __table_args__ = (PrimaryKeyConstraint("stock_id", "trade_date", "strategy"),)

    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    #: ``short`` | ``mid`` | ``long`` (configs/strategy_weights.yaml profiles).
    strategy: Mapped[str] = mapped_column(Text, nullable=False)
    technical_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    moneyflow_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    growth_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    quality_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    valuation_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    macro_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    governance_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    overall_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    #: Data-quality/confidence inputs in JSON (missing groups, red flags, …).
    data_flags: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    scoring_version: Mapped[str] = mapped_column(Text, nullable=False)


class StrategyRecommendation(TimestampMixin, Base):
    """Buy-zone/stop/target suggestion + explanation for one stock/strategy/day."""

    __tablename__ = "strategy_recommendations"
    __table_args__ = (PrimaryKeyConstraint("stock_id", "trade_date", "strategy"),)

    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    strategy: Mapped[str] = mapped_column(Text, nullable=False)
    #: A/B/C/D or NULL when the overall score is missing (no fabricated grade).
    grade: Mapped[str | None] = mapped_column(Text, nullable=True)
    buy_zone_low: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    buy_zone_high: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    #: Reward/risk ratio (target − entry) / (entry − stop); NULL if not computable.
    rr_ratio: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    reasons: Mapped[list[object] | None] = mapped_column(JSONB, nullable=True)
    risks: Mapped[list[object] | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    scoring_version: Mapped[str] = mapped_column(Text, nullable=False)


__all__ = ["StrategyScore", "StrategyRecommendation"]
