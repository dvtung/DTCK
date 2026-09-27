"""Integration: durable model-registry persistence against real PostgreSQL (T015b).

Skips when the database is unreachable or migration 0002 has not run.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import delete, text

from src.common.models.ml import ModelRegistry as ModelRegistryRow
from src.ml.model_registry import STATUS_APPROVED, ModelEntry, ModelRegistry
from src.ml.registry_store import hydrate_default_registry, load_entries, save_entry


def _entry(version: str) -> ModelEntry:
    return ModelEntry(
        model_id="price_direction_xgb",
        version=version,
        feature_version="feature_v1",
        training_data_version="td_v1",
        target="P(return > 0) over 5TD",
        horizon_days=5,
        model={"weights": [0.1]},
        calibrator=None,
        scaler=None,
        feature_columns=["close"],
        metrics={"roc_auc": 0.7},
        owner="system",
        status=STATUS_APPROVED,
        created_at=datetime(2026, 9, 27, 12, 0, 0),
    )


@pytest.fixture()
def registry_engine(db_ready: None):  # type: ignore[no-untyped-def]
    from apps.api.db import get_engine

    engine = get_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT artifact FROM model_registry LIMIT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"migration 0002 not applied (artifact column missing): {exc}")
    return engine


def test_save_then_load_roundtrip(registry_engine) -> None:  # type: ignore[no-untyped-def]
    entry = _entry("9.9.9-test")
    try:
        save_entry(entry, registry_engine)
        loaded = {e.version: e for e in load_entries(registry_engine)}
        assert "9.9.9-test" in loaded
        assert loaded["9.9.9-test"].metrics == {"roc_auc": 0.7}
        assert loaded["9.9.9-test"].feature_columns == ["close"]
        # Upsert idempotency: saving again must not duplicate the row.
        save_entry(entry, registry_engine)
        versions = [e.version for e in load_entries(registry_engine)]
        assert versions.count("9.9.9-test") == 1
    finally:
        with registry_engine.begin() as conn:
            conn.execute(
                delete(ModelRegistryRow).where(ModelRegistryRow.version == "9.9.9-test")
            )


def test_hydrate_default_registry_registers_savable_model(registry_engine) -> None:  # type: ignore[no-untyped-def]
    registry = ModelRegistry()
    try:
        save_entry(_entry("9.9.8-test"), registry_engine)
        # hydrate loads ALL rows into the given registry; verify ours is among them.
        count = hydrate_default_registry(registry_engine, registry=registry)
        assert count >= 1
        entry = registry.get("price_direction_xgb", "9.9.8-test")
        assert entry is not None
        assert entry.is_approvable()
    finally:
        with registry_engine.begin() as conn:
            conn.execute(
                delete(ModelRegistryRow).where(ModelRegistryRow.version == "9.9.8-test")
            )
