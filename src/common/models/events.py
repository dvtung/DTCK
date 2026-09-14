"""Corporate events & news models (DATABASE_SCHEMA §7)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, Date, ForeignKey, Numeric, PrimaryKeyConstraint, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from src.common.models.base import TIMESTAMPTZ, Base, TimestampMixin


class CorporateEvent(TimestampMixin, Base):
    """§7.1 — Corporate actions & events (earnings, dividends, splits, M&A, …)."""

    __tablename__ = "corporate_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    announced_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    details: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)


class News(TimestampMixin, Base):
    """§7.2 — News metadata + text (BM25/keyword search & provenance)."""

    __tablename__ = "news"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    sector_id: Mapped[int | None] = mapped_column(
        ForeignKey("sectors.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    importance: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    qdrant_point_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)


class NewsSymbol(Base):
    """§7.3 — Many-to-many link between news articles and stocks."""

    __tablename__ = "news_symbols"
    __table_args__ = (PrimaryKeyConstraint("news_id", "stock_id"),)

    news_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("news.id", ondelete="CASCADE"), nullable=False
    )
    stock_id: Mapped[int] = mapped_column(
        ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False
    )


__all__ = ["CorporateEvent", "News", "NewsSymbol"]
