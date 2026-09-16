"""Pydantic schemas for ML prediction API responses (spec §26, §28)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

__all__ = [
    "PredictionOut",
    "PredictionEvaluationOut",
    "ModelInfoOut",
]


class PredictionOut(BaseModel):
    """Single-symbol ML prediction response."""

    symbol: str
    trade_date: date
    model_id: str
    model_version: str
    feature_version: str
    target: str
    horizon_days: int
    expected_return: float | None = None
    probability_positive: float | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    calibrated: bool = True


class PredictionEvaluationOut(BaseModel):
    """Prediction evaluation outcome (spec §26)."""

    prediction_id: int
    symbol: str
    target: str
    predicted_value: float
    actual_value: float | None = None
    error: float | None = None
    hit: bool | None = None
    evaluated_at: datetime | None = None


class ModelInfoOut(BaseModel):
    """Model registry info."""

    model_id: str
    version: str
    feature_version: str
    target: str
    horizon_days: int
    status: str
    metrics: dict[str, float] = Field(default_factory=dict)
    created_at: datetime
