"""In-memory model registry for ML predictions (spec §40, ML_ARCHITECTURE.md §5).

Stores trained models with full versioning (model_id, version, feature_version,
training data version) and a status lifecycle:

    EXPERIMENTAL -> VALIDATING -> APPROVED -> PRODUCTION -> DEPRECATED

Models are kept in-process (deterministic, no external store needed for MVP-3
offline testing).  Each registered model bundles the sklearn/xgboost estimator,
calibrator, and feature column order so predictions are reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

__all__ = ["ModelEntry", "ModelRegistry"]

STATUS_EXPERIMENTAL = "EXPERIMENTAL"
STATUS_VALIDATING = "VALIDATING"
STATUS_APPROVED = "APPROVED"
STATUS_PRODUCTION = "PRODUCTION"
STATUS_DEPRECATED = "DEPRECATED"

VALID_TRANSITIONS: dict[str, set[str]] = {
    STATUS_EXPERIMENTAL: {STATUS_VALIDATING, STATUS_DEPRECATED},
    STATUS_VALIDATING: {STATUS_APPROVED, STATUS_DEPRECATED},
    STATUS_APPROVED: {STATUS_PRODUCTION, STATUS_DEPRECATED},
    STATUS_PRODUCTION: {STATUS_DEPRECATED},
    STATUS_DEPRECATED: set(),
}


@dataclass
class ModelEntry:
    """One entry in the model registry."""

    model_id: str
    version: str
    feature_version: str
    training_data_version: str
    target: str  # e.g. "return_positive_5d"
    horizon_days: int
    model: Any  # fitted estimator (xgboost/sklearn)
    calibrator: Any | None  # calibrated version of the model
    scaler: Any | None  # StandardScaler fitted during training
    feature_columns: list[str]
    metrics: dict[str, float] = field(default_factory=dict)
    parameters: dict[str, Any] = field(default_factory=dict)
    owner: str = "system"
    status: str = STATUS_EXPERIMENTAL
    created_at: datetime = field(default_factory=datetime.now)

    def promote(self, new_status: str) -> None:
        """Advance to ``new_status``, enforcing the lifecycle."""
        if new_status == self.status:
            return
        allowed = VALID_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Cannot promote {self.model_id} v{self.version} from "
                f"'{self.status}' to '{new_status}'"
            )
        self.status = new_status

    def is_approvable(self) -> bool:
        """True if model is APPROVED or PRODUCTION (safe to serve)."""
        return self.status in (STATUS_APPROVED, STATUS_PRODUCTION)


class ModelRegistry:
    """Process-wide model registry (in-memory, deterministic, no DB)."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], ModelEntry] = {}

    def register(self, entry: ModelEntry) -> None:
        """Register a model entry. Overwrites if same (model_id, version)."""
        self._entries[(entry.model_id, entry.version)] = entry

    def get(
        self, model_id: str, version: str | None = None
    ) -> ModelEntry | None:
        """Fetch a model entry; if ``version`` is None, fetch latest."""
        if version is not None:
            return self._entries.get((model_id, version))
        # Find latest version by created_at
        candidates = [
            e for (mid, _), e in self._entries.items() if mid == model_id
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda e: e.created_at, reverse=True)
        return candidates[0]

    def latest_approvable(self, model_id: str) -> ModelEntry | None:
        """Fetch the latest approvable model for a model_id."""
        candidates = [
            e for (mid, _), e in self._entries.items() if mid == model_id
        ]
        candidates.sort(key=lambda e: e.created_at, reverse=True)
        for entry in candidates:
            if entry.is_approvable():
                return entry
        return None

    def list_models(self) -> list[dict[str, Any]]:
        """List all model entries (metadata only, no pickled model)."""
        result = []
        for entry in sorted(self._entries.values(), key=lambda e: e.created_at, reverse=True):
            result.append(
                {
                    "model_id": entry.model_id,
                    "version": entry.version,
                    "feature_version": entry.feature_version,
                    "target": entry.target,
                    "horizon_days": entry.horizon_days,
                    "status": entry.status,
                    "metrics": entry.metrics,
                    "owner": entry.owner,
                    "created_at": entry.created_at.isoformat(),
                }
            )
        return result

    def count(self) -> int:
        return len(self._entries)
