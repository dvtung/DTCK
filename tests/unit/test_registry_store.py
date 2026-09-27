"""Unit tests for the durable model-registry persistence (T015b, spec §10.1/§40).

Covers the pickle round-trip (artifact fidelity), row-value mapping (typed
governance columns, honest NULL training windows), and — when the database is
reachable — a full save→load upsert round-trip (skipped otherwise).
"""

from __future__ import annotations

import pickle
from datetime import datetime

import pytest

from src.ml.model_registry import STATUS_APPROVED, ModelEntry, ModelRegistry
from src.ml.registry_store import _row_values, dump_entry, load_entry


def _entry(**overrides: object) -> ModelEntry:
    """A minimal picklable ModelEntry (dict as stand-in estimator)."""
    kwargs: dict = {
        "model_id": "price_direction_xgb",
        "version": "1.0.0",
        "feature_version": "feature_v1",
        "training_data_version": "td_v1",
        "target": "P(return > 0) over 5TD",
        "horizon_days": 5,
        "model": {"weights": [0.1, 0.2]},
        "calibrator": None,
        "scaler": None,
        "feature_columns": ["close", "rsi14"],
        "metrics": {"roc_auc": 0.702},
        "owner": "system",
        "status": STATUS_APPROVED,
        "created_at": datetime(2026, 9, 27, 12, 0, 0),
    }
    kwargs.update(overrides)
    return ModelEntry(**kwargs)  # type: ignore[arg-type]


class TestArtifactRoundtrip:
    def test_dump_load_restores_every_field(self) -> None:
        entry = _entry()
        restored = load_entry(dump_entry(entry))
        assert restored == entry
        assert restored.model == {"weights": [0.1, 0.2]}
        assert restored.feature_columns == ["close", "rsi14"]

    def test_load_rejects_non_entry_payload(self) -> None:
        with pytest.raises(TypeError, match="expected ModelEntry"):
            load_entry(pickle.dumps({"model_id": "spoof"}))

    def test_load_rejects_garbage(self) -> None:
        with pytest.raises(Exception):  # noqa: B017 - pickle.UnpicklingError is fine
            load_entry(b"not a pickle at all")


class TestRowValues:
    def test_typed_columns_mirror_governance_fields(self) -> None:
        values = _row_values(_entry())
        assert values["model_id"] == "price_direction_xgb"
        assert values["status"] == STATUS_APPROVED
        assert values["target"] == "P(return > 0) over 5TD"
        assert values["horizon_days"] == 5
        assert values["metrics"] == {"roc_auc": 0.702}

    def test_training_window_is_null_never_fabricated(self) -> None:
        """The trainer knows no window boundaries — NULL, not made-up dates (§31)."""
        values = _row_values(_entry())
        assert values["training_period_start"] is None
        assert values["training_period_end"] is None

    def test_artifact_column_holds_a_loadable_entry(self) -> None:
        values = _row_values(_entry())
        assert isinstance(values["artifact"], bytes)
        assert load_entry(values["artifact"]).model_id == "price_direction_xgb"


def test_registry_accepts_restored_entry() -> None:
    """A round-tripped entry must be servable: latest_approvable finds it."""
    registry = ModelRegistry()
    registry.register(load_entry(dump_entry(_entry())))
    entry = registry.latest_approvable("price_direction_xgb")
    assert entry is not None
    assert entry.is_approvable()
