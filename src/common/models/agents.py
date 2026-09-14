"""Agent governance models (DATABASE_SCHEMA §13): registry, runs, tool calls."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, PrimaryKeyConstraint, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from src.common.models.base import TIMESTAMPTZ, Base


class AgentRegistry(Base):
    """§13.1 — Registered agent definitions with their governance metadata."""

    __tablename__ = "agent_registry"
    __table_args__ = (PrimaryKeyConstraint("agent_id", "version"),)

    agent_id: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    available_tools: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    allowed_data: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    output_schema_ref: Mapped[str] = mapped_column(Text, nullable=False)
    evaluation_score: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 3), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)


class AgentRun(Base):
    """§13.2 — Agent execution audit record (§31)."""

    __tablename__ = "agent_runs"

    agent_run_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True)
    user_request: Mapped[str] = mapped_column(Text, nullable=False)
    agent_id: Mapped[str] = mapped_column(Text, nullable=False)
    agent_version: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    model_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_output: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_usage: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)


class AgentToolCall(Base):
    """§13.3 — Tool invocations within an agent run (§22)."""

    __tablename__ = "agent_tool_calls"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    agent_run_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("agent_runs.agent_run_id", ondelete="CASCADE"),
        nullable=False,
    )
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    tool_input: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    tool_output: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    called_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


__all__ = ["AgentRegistry", "AgentRun", "AgentToolCall"]
