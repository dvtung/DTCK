"""Email notifications models (recipients, smtp configs, schedules, send logs)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from src.common.models.base import AuditMixin, Base, TimestampMixin


class EmailRecipient(AuditMixin, Base):
    """Subscribers receiving automated market overview reports."""

    __tablename__ = "email_recipients"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class EmailSmtpConfig(AuditMixin, Base):
    """SMTP configuration for dispatching automated emails (e.g. Gmail SMTP)."""

    __tablename__ = "email_smtp_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    smtp_server: Mapped[str] = mapped_column(String(255), nullable=False, default="smtp.gmail.com")
    smtp_port: Mapped[int] = mapped_column(Integer, nullable=False, default=587)
    sender_email: Mapped[str] = mapped_column(String(255), nullable=False)
    sender_password: Mapped[str] = mapped_column(String(255), nullable=False)
    sender_name: Mapped[str] = mapped_column(
        String(255), nullable=False, default="DTCK Market Intel"
    )
    use_tls: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    use_ssl: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class EmailScheduleConfig(AuditMixin, Base):
    """Schedule rules for automatic market reports (Mon-Fri 08:00 and 15:30)."""

    __tablename__ = "email_schedule_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    morning_hour: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    morning_minute: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    afternoon_hour: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    afternoon_minute: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    days_of_week: Mapped[str] = mapped_column(String(50), default="mon-fri", nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class EmailSendLog(TimestampMixin, Base):
    """Audit log of sent emails."""

    __tablename__ = "email_send_logs"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # SUCCESS, FAILED
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
