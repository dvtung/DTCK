"""Reference model tables (DATABASE_SCHEMA §3): exchanges, sectors, industries, stocks."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, SmallInteger, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.common.models.base import AuditMixin, Base


class Exchange(Base):
    """§3.1 — Market exchanges: HOSE, HNX, UPCOM."""

    __tablename__ = "exchanges"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self) -> str:
        return f"<Exchange {self.code}>"


class Sector(Base):
    """§3.2 — Sector taxonomy row (ICB or custom). Parent link enables industry rollup."""

    __tablename__ = "sectors"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("sectors.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Sector {self.code}>"


class Industry(Base):
    """§3.2 — Industry taxonomy row (children of a Sector)."""

    __tablename__ = "industries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("sectors.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Industry {self.code}>"


class Stock(AuditMixin, Base):
    """§3.3 — Listed instruments. Delisted rows are kept (anti survivorship bias)."""

    __tablename__ = "stocks"
    __table_args__ = (UniqueConstraint("symbol", "exchange_id", name="uq_stocks_symbol_exchange"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    exchange_id: Mapped[int] = mapped_column(
        ForeignKey("exchanges.id", ondelete="RESTRICT"), nullable=False
    )
    company_name: Mapped[str] = mapped_column(Text, nullable=False)
    sector_id: Mapped[int | None] = mapped_column(
        ForeignKey("sectors.id", ondelete="RESTRICT"), nullable=True
    )
    industry_id: Mapped[int | None] = mapped_column(
        ForeignKey("industries.id", ondelete="RESTRICT"), nullable=True
    )
    listed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delisted_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="ACTIVE",
    )
    is_vn30: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_vn100: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    def __repr__(self) -> str:
        return f"<Stock {self.symbol}>"


__all__ = ["Exchange", "Sector", "Industry", "Stock"]
