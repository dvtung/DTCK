"""RAG / evidence models (DATABASE_SCHEMA §12): documents, evidence."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from src.common.models.base import TIMESTAMPTZ, Base, TimestampMixin


class Document(TimestampMixin, Base):
    """§12.1 — Metadata for anything embedded into Qdrant (vectors live in Qdrant)."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int | None] = mapped_column(
        ForeignKey("stocks.id", ondelete="SET NULL"), nullable=True
    )
    doc_type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    qdrant_point_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)


class Evidence(TimestampMixin, Base):
    """§12.2 — Evidence engine records backing claims (§19)."""

    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    data_timestamp: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    linked_entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    linked_entity_id: Mapped[str] = mapped_column(Text, nullable=False)


__all__ = ["Document", "Evidence"]
