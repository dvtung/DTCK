"""Initial schema: create every DATABASE_SCHEMA table + convert time-series to hypertables.

STEP 2 (DATABASE DESIGN) — T003 initial migration. Table definitions come from the
SQLAlchemy models (``src.common.models.Base.metadata``) which are the single source
of truth. Hypertables are created via TimescaleDB ``create_hypertable`` per
`docs/DATABASE_SCHEMA.md` §17.

Revision ID: 0001_initial_schema
Revises: (none)
Create Date: 2026-09-13
"""

from __future__ import annotations

from alembic import op

from src.common.models import Base

# revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

# table_name -> (partition_column, chunk_time_interval value) per §17. The value
# is the raw interval literal (e.g. "1 month") rendered as `INTERVAL '<value>'`.
# ``predictions`` is intentionally omitted: it is a regular (non-hypertable) table
# because TimescaleDB requires the partitioning column in every unique index and
# ``prediction_evaluations.prediction_id`` references ``predictions.id`` (see
# memory-bank/decisions.md).
HYPERTABLES: dict[str, tuple[str, str]] = {
    "prices": ("trade_date", "1 month"),
    "adjusted_prices": ("trade_date", "1 month"),
    "index_prices": ("trade_date", "1 month"),
    "foreign_flows": ("trade_date", "1 month"),
    "prop_trading_flows": ("trade_date", "1 month"),
    "valuation_daily": ("trade_date", "1 month"),
    "macro_indicators": ("period_date", "1 year"),
    "features": ("trade_date", "1 month"),
    "factor_scores": ("trade_date", "1 month"),
    "signals": ("trade_date", "1 month"),
    "market_regimes": ("trade_date", "1 year"),
    "portfolio_snapshots": ("snapshot_date", "1 month"),
}


def upgrade() -> None:
    bind = op.get_bind()

    # Prerequisite extensions (idempotent).
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # Create every table in dependency order from the model metadata.
    Base.metadata.create_all(bind=bind)

    # Convert time-series tables into TimescaleDB hypertables. The table/column
    # identifiers come from the constants above (no user input / injection risk).
    for table_name, (partition_column, chunk_interval) in HYPERTABLES.items():
        op.execute(
            f"SELECT create_hypertable('{table_name}', '{partition_column}', "
            f"chunk_time_interval => INTERVAL '{chunk_interval}', "
            f"if_not_exists => TRUE, migrate_data => TRUE)"
        )


def downgrade() -> None:
    """Drop every table (dropping a hypertable removes its chunks)."""
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
