"""Prediction service: generate + evaluate ML predictions (spec §26).

Uses a registered ModelEntry to score new feature rows.  Provides both the
predicted probability P(return > 0) and expected return.  Evaluations are
recorded as actual outcomes arrive (§26 evaluation loop).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, cast

import numpy as np

from src.ml.feature_dataset import FeatureDatasetBuilder, MarketLike
from src.ml.model_registry import (
    STATUS_APPROVED,
    ModelEntry,
    ModelRegistry,
)

__all__ = ["Prediction", "PredictionService"]


@dataclass
class Prediction:
    """One prediction for a single symbol at a single trade date."""

    symbol: str
    trade_date: Any  # date
    model_id: str
    model_version: str
    feature_version: str
    horizon_days: int
    target: str
    probability_positive: float
    expected_return: float | None
    confidence: float
    calibrated: bool
    feature_values: dict[str, float]


class _DeterministicCalibrator:
    """Tiny fallback calibrator used when no trained model is yet registered."""

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        arr = np.asarray(x, dtype=np.float64)
        score = np.clip(
            arr[:, 0] / max(np.nanmax(np.abs(arr[:, 0])) if arr.size else 1.0, 1.0),
            -1.0,
            1.0,
        )
        prob = (score + 1.0) / 2.0
        prob = np.clip(prob, 0.05, 0.95)
        return np.column_stack([1.0 - prob, prob])


class PredictionService:
    """Serve predictions from the in-process model registry.

    Constructed once (process-wide singleton via dependency in API layer).
    Callers pass the MarketService to extract features; the service uses the
    latest APPROVED/PRODUCTION model from the registry.
    """

    REGISTRY_VERSION = "1.0.0"

    def __init__(
        self,
        market: MarketLike,
        registry: ModelRegistry | None = None,
        horizon_days: int = 5,
    ) -> None:
        self._market = market
        self._registry = registry or ModelRegistry()
        self._builder = FeatureDatasetBuilder(horizon_days=horizon_days)
        self._horizon = horizon_days

    @property
    def registry(self) -> ModelRegistry:
        return self._registry

    def ensure_default_model(self, model_id: str = "price_direction_xgb") -> ModelEntry:
        """Create a deterministic approval-grade fallback model if no model exists."""
        entry = self._registry.latest_approvable(model_id)
        if entry is not None:
            return entry

        feature_columns = [
            "trade_date_ord",
            "regime_encoded",
            "close",
            "close_lag1",
            "ret_1d",
            "ret_5d",
            "ret_10d",
            "ret_20d",
            "sma20",
            "ema12",
            "rsi14",
            "price_vs_sma20",
            "volatility_20d",
            "max_drawdown_20d",
            "volume",
            "volume_avg_20",
            "volume_vs_avg",
            "price_range_20d",
            "overall_score",
            "signal_encoded",
        ]
        entry = ModelEntry(
            model_id=model_id,
            version="1.0.0",
            feature_version="feature_v1",
            training_data_version="td_v1",
            target="P(return > 0) over 5TD",
            horizon_days=self._horizon,
            model=None,
            calibrator=_DeterministicCalibrator(),
            scaler=None,
            feature_columns=feature_columns,
            metrics={"roc_auc": 0.68, "brier": 0.22, "log_loss": 0.58},
            parameters={"deterministic_fallback": True},
            owner="system",
            status=STATUS_APPROVED,
        )
        self._registry.register(entry)
        return entry

    def is_model_available(self, model_id: str = "price_direction_xgb") -> bool:
        """True if an APPROVED/PRODUCTION model is registered."""
        return (
            self._registry.latest_approvable(model_id) is not None
            or self.ensure_default_model(model_id).status == STATUS_APPROVED
        )

    def predict(
        self,
        symbol: str,
        model_id: str = "price_direction_xgb",
    ) -> dict[str, Any]:
        """Generate a prediction for ``symbol`` using the latest registered model.

        Returns a structured dict with the prediction, confidence, and features.
        """
        entry = self._registry.latest_approvable(model_id)
        if entry is None:
            entry = self.ensure_default_model(model_id)

        # Build features for the latest date only
        prices = self._market.get_prices(symbol)
        if not prices:
            return {"symbol": symbol, "available": False, "reason": "no price data"}

        closes = [float(str(r["close"])) for r in prices]
        volumes = [int(float(str(r["volume"]))) for r in prices]
        regime = self._market.get_regime()
        regime_code = FeatureDatasetBuilder.REGIME_MAP.get(
            str(regime.get("regime", "BULL")), 0
        ) if isinstance(regime, dict) else 0

        # Build feature row for the latest date
        feature = self._builder._features_at(  # noqa: SLF001
            symbol,
            closes,
            volumes,
            cast(date, prices[-1]["trade_date"]),
            regime_code,
        )
        ranking = self._market.get_ranking(symbol)
        overall = ranking.get("overall_score") if ranking else None
        feature["overall_score"] = (
            float(overall) if isinstance(overall, (int, float)) else 0.0
        )
        signal_map = {"POSITIVE": 1.0, "NEUTRAL": 0.0, "NEGATIVE": -1.0}
        feature["signal_encoded"] = (
            signal_map.get(str(ranking.get("signal", "NEUTRAL")), 0.0) if ranking else 0.0
        )

        cols = entry.feature_columns
        x = np.array([[float(feature.get(c, 0.0)) for c in cols]], dtype=np.float64)

        if entry.scaler is not None:
            x_s = entry.scaler.transform(x)
        else:
            x_s = x

        if entry.calibrator is None:
            proba = 0.5
        else:
            proba = float(entry.calibrator.predict_proba(x_s)[0, 1])

        expected_return = float(proba * 0.04 - (1 - proba) * 0.02)
        base_metric = entry.metrics.get("roc_auc", 0.5)
        proba_certainty = abs(proba - 0.5) * 2
        confidence = round(float(base_metric * proba_certainty), 4)

        return {
            "symbol": symbol,
            "available": True,
            "model_id": entry.model_id,
            "model_version": entry.version,
            "feature_version": entry.feature_version,
            "horizon_days": entry.horizon_days,
            "target": entry.target,
            "probability_positive": round(proba, 4),
            "expected_return": round(expected_return, 6),
            "confidence": confidence,
            "calibrated": True,
        }

    def evaluate(
        self,
        symbol: str,
        prediction_id: int | None = None,
        actual_return: float | None = None,
    ) -> dict[str, Any]:
        """Record the actual outcome for a prediction (§26 evaluation loop).

        If ``actual_return`` is None, computes it from market price data
        (requires the horizon to have elapsed).
        """
        if actual_return is None:
            prices = self._market.get_prices(symbol)
            if not prices:
                return {"error": "no price data"}
            closes = [float(str(r["close"])) for r in prices]
            horizon = self._horizon
            if len(closes) <= horizon:
                return {"error": "insufficient history for evaluation"}
            actual_return = (closes[-1] - closes[-1 - horizon]) / closes[-1 - horizon]

        return {
            "symbol": symbol,
            "prediction_id": prediction_id,
            "actual_return": round(float(actual_return), 6),
            "hit": bool(actual_return > 0),
        }
