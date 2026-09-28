"""Add the noon report window to email_schedule_configs.

Three daily report windows (Asia/Ho_Chi_Minh, Mon–Fri): 08:00 previous-session
summary, 12:30 morning session, 16:30 afternoon session.  The original table only
carried a morning and an afternoon pair.

Revision ID: 0004_email_schedule_noon
Revises: 0003_email_notifications
Create Date: 2026-09-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0004_email_schedule_noon"
down_revision = "0003_email_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_schedule_configs",
        sa.Column("noon_hour", sa.Integer(), nullable=False, server_default="12"),
    )
    op.add_column(
        "email_schedule_configs",
        sa.Column("noon_minute", sa.Integer(), nullable=False, server_default="30"),
    )
    # Existing rows carried the old 15:30 afternoon default; the afternoon window
    # is now 16:30 so the report follows the post-close scoring run.
    op.execute("UPDATE email_schedule_configs SET afternoon_hour = 16 WHERE afternoon_hour = 15")
    op.alter_column("email_schedule_configs", "afternoon_hour", server_default="16")


def downgrade() -> None:
    op.alter_column("email_schedule_configs", "afternoon_hour", server_default="15")
    op.drop_column("email_schedule_configs", "noon_minute")
    op.drop_column("email_schedule_configs", "noon_hour")
