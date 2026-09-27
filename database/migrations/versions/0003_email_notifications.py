"""Add email notification tables (recipients, smtp configs, schedule, logs).

Revision ID: 0003_email_notifications
Revises: 0002_model_registry_artifact
Create Date: 2026-09-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "0003_email_notifications"
down_revision = "0002_model_registry_artifact"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_recipients",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_email_recipients_email", "email_recipients", ["email"])

    op.create_table(
        "email_smtp_configs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "smtp_server", sa.String(length=255), nullable=False, server_default="smtp.gmail.com"
        ),
        sa.Column("smtp_port", sa.Integer(), nullable=False, server_default="587"),
        sa.Column("sender_email", sa.String(length=255), nullable=False),
        sa.Column("sender_password", sa.String(length=255), nullable=False),
        sa.Column(
            "sender_name", sa.String(length=255), nullable=False, server_default="DTCK Market Intel"
        ),
        sa.Column("use_tls", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("use_ssl", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "email_schedule_configs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("morning_hour", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("morning_minute", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("afternoon_hour", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("afternoon_minute", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("days_of_week", sa.String(length=50), nullable=False, server_default="mon-fri"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "email_send_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("recipient_email", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_email_send_logs_recipient_email", "email_send_logs", ["recipient_email"])


def downgrade() -> None:
    op.drop_index("ix_email_send_logs_recipient_email", table_name="email_send_logs")
    op.drop_table("email_send_logs")
    op.drop_table("email_schedule_configs")
    op.drop_table("email_smtp_configs")
    op.drop_index("ix_email_recipients_email", table_name="email_recipients")
    op.drop_table("email_recipients")
