"""Add strategy scoring tables + ``financial_statements.published_at``.

New module "Chấm điểm & Gợi ý cổ phiếu đa chiến lược" (multi-profile scoring).
Tables are deliberately **separate** from ``factor_scores`` so the existing
six-dimension ranking and ``/api/v1/stocks/ranked`` remain untouched.

* ``strategy_scores`` — one row per (stock, trade_date, strategy profile);
  converted to a TimescaleDB hypertable on ``trade_date``.
* ``strategy_recommendations`` — grade/buy-zone/stop/target + explanation.
* ``financial_statements.published_at`` — look-ahead guard for fundamental
  features (nullable: unknown publish dates stay NULL, never guessed).

Revision ID: 0005_strategy_scoring
Revises: 0004_email_schedule_noon
Create Date: 2026-10-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "0005_strategy_scoring"
down_revision = "0004_email_schedule_noon"
branch_labels = None
depends_on = None

#: Hypertable conversions owned by this revision (table -> partition column).
HYPERTABLES: dict[str, tuple[str, str]] = {
    "strategy_scores": ("trade_date", "1 month"),
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    # 0001 runs Base.metadata.create_all, so on a FRESH database these tables
    # already exist — mirror 0002's idempotency for both paths.
    if not inspector.has_table("strategy_scores"):
        op.create_table(
            "strategy_scores",
            sa.Column("stock_id", sa.Integer(), sa.ForeignKey("stocks.id"), nullable=False),
            sa.Column("trade_date", sa.Date(), nullable=False),
            sa.Column("strategy", sa.Text(), nullable=False),
            sa.Column("technical_score", sa.Numeric(6, 2), nullable=True),
            sa.Column("moneyflow_score", sa.Numeric(6, 2), nullable=True),
            sa.Column("growth_score", sa.Numeric(6, 2), nullable=True),
            sa.Column("quality_score", sa.Numeric(6, 2), nullable=True),
            sa.Column("valuation_score", sa.Numeric(6, 2), nullable=True),
            sa.Column("macro_score", sa.Numeric(6, 2), nullable=True),
            sa.Column("governance_score", sa.Numeric(6, 2), nullable=True),
            sa.Column("overall_score", sa.Numeric(6, 2), nullable=True),
            sa.Column("data_flags", JSONB(), nullable=True),
            sa.Column("scoring_version", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("stock_id", "trade_date", "strategy"),
        )

    if not inspector.has_table("strategy_recommendations"):
        op.create_table(
            "strategy_recommendations",
            sa.Column("stock_id", sa.Integer(), sa.ForeignKey("stocks.id"), nullable=False),
            sa.Column("trade_date", sa.Date(), nullable=False),
            sa.Column("strategy", sa.Text(), nullable=False),
            sa.Column("grade", sa.Text(), nullable=True),
            sa.Column("buy_zone_low", sa.Numeric(18, 2), nullable=True),
            sa.Column("buy_zone_high", sa.Numeric(18, 2), nullable=True),
            sa.Column("stop_loss", sa.Numeric(18, 2), nullable=True),
            sa.Column("target_price", sa.Numeric(18, 2), nullable=True),
            sa.Column("rr_ratio", sa.Numeric(8, 2), nullable=True),
            sa.Column("reasons", JSONB(), nullable=True),
            sa.Column("risks", JSONB(), nullable=True),
            sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
            sa.Column("scoring_version", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("stock_id", "trade_date", "strategy"),
        )

    for table_name, (partition_column, chunk_interval) in HYPERTABLES.items():
        op.execute(
            f"SELECT create_hypertable('{table_name}', '{partition_column}', "
            f"chunk_time_interval => INTERVAL '{chunk_interval}', "
            f"if_not_exists => TRUE, migrate_data => TRUE)"
        )

    op.execute(
        "ALTER TABLE financial_statements ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE financial_statements DROP COLUMN IF EXISTS published_at")
    # Dropping a hypertable removes its chunks too.
    op.execute("DROP TABLE IF EXISTS strategy_recommendations CASCADE")
    op.execute("DROP TABLE IF EXISTS strategy_scores CASCADE")
