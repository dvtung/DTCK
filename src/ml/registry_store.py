"""Durable model-registry persistence (spec §10.1/§40, T015b).

The in-memory registry in :mod:`src.ml.model_registry` dies with the process
that trained the model, so ``train-model`` runs were invisible to the API —
``/predictions`` kept serving the deterministic stub.  This module mirrors each
:class:`~src.ml.model_registry.ModelEntry` into the ``model_registry`` table
(typed governance columns for querying + a pickled artifact for serving) and
hydrates the process registry from it at API startup.

Security: rows are only ever unpickled from the application's **own** database
(written by our own worker).  Never point this at an untrusted DB — pickle can
execute arbitrary code on load (§32: DB credentials are app-scoped and the
instance is inside the Docker network).
"""

from __future__ import annotations

import logging
import pickle
from typing import Any

from sqlalchemy import Engine, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.common.models.ml import ModelRegistry as ModelRegistryRow
from src.ml.model_registry import ModelEntry, ModelRegistry, get_default_registry

__all__ = ["dump_entry", "hydrate_default_registry", "load_entry", "load_entries", "save_entry"]

logger = logging.getLogger(__name__)


def dump_entry(entry: ModelEntry) -> bytes:
    """Serialize a full ``ModelEntry`` (estimator, calibrator, scaler, columns)."""
    return pickle.dumps(entry, protocol=pickle.HIGHEST_PROTOCOL)


def load_entry(artifact: bytes) -> ModelEntry:
    """Deserialize an artifact, rejecting anything that is not a ``ModelEntry``."""
    obj = pickle.loads(artifact)  # noqa: S301 — own-DB rows only (module docstring)
    if not isinstance(obj, ModelEntry):
        raise TypeError(f"artifact is {type(obj).__name__}, expected ModelEntry")
    return obj


def _row_values(entry: ModelEntry) -> dict[str, Any]:
    """Typed columns (queryable without unpickling) + the serving artifact."""
    return {
        "model_id": entry.model_id,
        "version": entry.version,
        "training_data_version": entry.training_data_version,
        "feature_version": entry.feature_version,
        # Window boundaries are unknown to the trainer — NULL, never fabricated (§31).
        "training_period_start": None,
        "training_period_end": None,
        "metrics": dict(entry.metrics),
        "parameters": dict(entry.parameters),
        "owner": entry.owner,
        "status": entry.status,
        "target": entry.target,
        "horizon_days": entry.horizon_days,
        "artifact": dump_entry(entry),
        "created_at": entry.created_at,
    }


def save_entry(entry: ModelEntry, engine: Engine) -> None:
    """Upsert one registry entry (idempotent on ``(model_id, version)``)."""
    values = _row_values(entry)
    stmt = pg_insert(ModelRegistryRow).values(**values)
    update_cols = {key: stmt.excluded[key] for key in values if key != "model_id"}
    stmt = stmt.on_conflict_do_update(
        index_elements=["model_id", "version"], set_=update_cols
    )
    with engine.begin() as conn:
        conn.execute(stmt)


def load_entries(engine: Engine) -> list[ModelEntry]:
    """Read every persisted entry that carries an artifact (newest first).

    A row whose artifact fails to unpickle (e.g. dependency version drift) is
    skipped with a warning — one bad row must not hide healthy models.
    """
    entries: list[ModelEntry] = []
    with Session(engine) as session:
        rows = session.execute(
            select(ModelRegistryRow)
            .where(ModelRegistryRow.artifact.is_not(None))
            .order_by(ModelRegistryRow.created_at.desc())
        ).scalars()
        for row in rows:
            artifact = row.artifact
            if artifact is None:  # narrowed: the SELECT filter is not visible to mypy
                continue
            try:
                entries.append(load_entry(artifact))
            except Exception as exc:  # noqa: BLE001 — skip and report the row
                logger.warning(
                    "skipping registry row %s@%s: %s", row.model_id, row.version, exc
                )
    return entries


def hydrate_default_registry(engine: Engine, registry: ModelRegistry | None = None) -> int:
    """Load persisted entries into the process registry; return rows loaded.

    Best-effort by contract (ADR-001): callers wrap this so an unreachable DB
    leaves the API serving the deterministic fallback instead of crashing.
    """
    target = registry or get_default_registry()
    entries = load_entries(engine)
    for entry in entries:
        target.register(entry)
    if entries:
        logger.info("hydrated %d model(s) from the registry table", len(entries))
    return len(entries)
