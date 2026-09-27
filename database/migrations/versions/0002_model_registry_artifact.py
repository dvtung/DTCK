"""Add serving-artifact columns to model_registry (T015b, spec §10.1/§40).

The in-memory registry (``src/ml/model_registry.py``) died with the process that
trained the model, so an APPROVED training run was invisible to the API.  This
migration adds the columns needed to persist ``ModelEntry`` rows so the API can
hydrate its registry at startup:

* ``artifact`` — pickled ``ModelEntry`` (estimator + calibrator + scaler +
  feature columns); the governance columns below are duplicated into typed
  columns for querying without unpickling,
* ``target`` / ``horizon_days`` — what the model predicts (§14),
* ``training_period_*`` become nullable: the trainer does not know the exact
  window boundaries, and fabricating dates would violate §31 honesty.

Revision ID: 0002_model_registry_artifact
Revises: 0001_initial_schema
Create Date: 2026-09-27
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_model_registry_artifact"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0001 creates tables via Base.metadata.create_all, so on a FRESH database
    # these columns already exist — IF NOT EXISTS keeps 0002 idempotent for
    # both paths (existing 0001-pinned DBs and new clones).
    op.execute("ALTER TABLE model_registry ADD COLUMN IF NOT EXISTS artifact BYTEA")
    op.execute("ALTER TABLE model_registry ADD COLUMN IF NOT EXISTS target TEXT")
    op.execute("ALTER TABLE model_registry ADD COLUMN IF NOT EXISTS horizon_days INTEGER")
    # The trainer has no training-window metadata; existing NOT NULLs would
    # force fabricated dates.  Nullable is the honest contract (§31).
    op.execute("ALTER TABLE model_registry ALTER COLUMN training_period_start DROP NOT NULL")
    op.execute("ALTER TABLE model_registry ALTER COLUMN training_period_end DROP NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE model_registry ALTER COLUMN training_period_start SET NOT NULL")
    op.execute("ALTER TABLE model_registry ALTER COLUMN training_period_end SET NOT NULL")
    op.execute("ALTER TABLE model_registry DROP COLUMN IF EXISTS horizon_days")
    op.execute("ALTER TABLE model_registry DROP COLUMN IF EXISTS target")
    op.execute("ALTER TABLE model_registry DROP COLUMN IF EXISTS artifact")
