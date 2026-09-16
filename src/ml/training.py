"""ML training + calibration (spec §14.3, ML_ARCHITECTURE.md §4).

Temporal train/validation/test split (no shuffle across time per §17),
XGBoost classifier, Platt/isotonic calibration, and investment-oriented
metrics (AUC, Brier, log-loss, accuracy, precision, recall, F1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler

from src.ml.feature_dataset import FEATURE_VERSION, Dataset
from src.ml.model_registry import ModelEntry, ModelRegistry

__all__ = [
    "ModelTrainer",
    "TrainingResult",
    "TRAINING_DATA_VERSION",
]

TRAINING_DATA_VERSION = "td_v1"


def _make_xgboost(random_state: int) -> Any:
    import xgboost as xgb

    return xgb.XGBClassifier(
        n_estimators=50,
        max_depth=3,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=random_state,
        eval_metric="logloss",
        n_jobs=1,
    )


def _make_lightgbm(random_state: int) -> Any | None:
    """LightGBM candidate; ``None`` when the optional extra is not installed."""
    try:
        import lightgbm as lgb
    except ModuleNotFoundError:  # optional [ml] extra; xgboost alone suffices
        return None
    return lgb.LGBMClassifier(
        n_estimators=50,
        max_depth=3,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=random_state,
        n_jobs=1,
        verbose=-1,
        min_child_samples=5,
    )


class _SigmoidCalibrator:
    """Platt-style calibrator (sklearn-version independent).

    Frozen linear map s -> sigmoid(a*s + b) fitted on validation scores by
    one-feature logistic regression.  Replaces ``CalibratedClassifierCV`` with
    ``cv="prefit"``, which scikit-learn 1.8+ removed, with a deterministic
    dependency-stable implementation.
    """

    def __init__(self) -> None:
        self.a = 1.0
        self.b = 0.0

    def fit(self, proba: Any, y: Any) -> _SigmoidCalibrator:
        from sklearn.linear_model import LogisticRegression

        p = np.asarray(proba, dtype=np.float64).reshape(-1, 1)
        t = np.asarray(y, dtype=np.float64).ravel()
        lr = LogisticRegression(C=1e6, max_iter=1000)
        lr.fit(p, t)
        self.a = float(lr.coef_[0, 0])
        self.b = float(lr.intercept_[0])
        return self

    def transform(self, x: Any) -> Any:
        """Map raw positive-class scores through the frozen sigmoid."""
        arr = np.asarray(x, dtype=np.float64)
        prob = 1.0 / (1.0 + np.exp(-(self.a * arr + self.b)))
        return np.clip(prob, 1e-6, 1.0 - 1e-6)

    def predict_proba(self, x: Any) -> Any:
        prob = self.transform(x)
        return np.column_stack([1.0 - prob, prob])


class _CalibratedClassifier:
    """Frozen estimator + calibrator pair exposing a sklearn-like API."""

    def __init__(self, model: Any, calibrator: _SigmoidCalibrator) -> None:
        self._model = model
        self._calibrator = calibrator
        self.classes_ = [0, 1]

    def _scores(self, x: Any) -> Any:
        return np.asarray(self._model.predict_proba(x), dtype=np.float64)[:, 1]

    def predict_proba(self, x: Any) -> Any:
        prob = self._calibrator.transform(self._scores(x))
        return np.column_stack([1.0 - prob, prob])

    def predict(self, x: Any) -> Any:
        return (self.predict_proba(x)[:, 1] >= 0.5).astype(int)



@dataclass
class TrainingResult:
    """Outcome of training + calibration on a Dataset."""

    model: object
    calibrator: object
    scaler: StandardScaler
    feature_columns: list[str]
    metrics: dict[str, float]
    split_sizes: dict[str, int]
    trained_at: datetime = field(default_factory=datetime.now)


class ModelTrainer:
    """Train an XGBoost classifier with temporal splits + calibration.

    Temporal split: first 60% of dates for training, next 20% for validation,
    last 20% for test.  No shuffling across time (§17).
    """

    def __init__(self, horizon_days: int = 5, random_state: int = 42) -> None:
        self.horizon_days = horizon_days
        self.random_state = random_state

    _VALID_TARGET_COLS = ("target_positive",)

    def train(
        self,
        dataset: Dataset,
        model_id: str = "price_direction_xgb",
        target_col: str = "target_positive",
    ) -> TrainingResult:
        """Train + calibrate; return the fitted model with test metrics."""
        del model_id  # naming is applied by train_and_register / registry
        if target_col not in self._VALID_TARGET_COLS:
            raise ValueError(
                f"target_col must be one of {self._VALID_TARGET_COLS}, got {target_col!r}"
            )
        x = dataset.features.reset_index(drop=True)
        y = dataset.target_positive.reset_index(drop=True)
        meta = dataset.metadata.reset_index(drop=True)
        if len(x) != len(y) or len(x) != len(meta):
            raise ValueError(
                "features, targets and metadata must have the same number of rows "
                f"(got {len(x)}, {len(y)}, {len(meta)})"
            )
        y = y.astype(int)
        labels = sorted(set(y.tolist()))
        if any(label not in (0, 1) for label in labels):
            raise ValueError(f"target_positive labels must be 0/1, got {labels}")

        # Temporal split on UNIQUE trade dates (rows repeat per symbol, so
        # splitting on row counts could put one date into two partitions).
        dates = sorted(set(meta["trade_date"].tolist()))
        if len(dates) < 3:
            raise ValueError(
                f"at least 3 distinct trade dates are required, got {len(dates)}"
            )
        train_cutoff = int(len(dates) * 0.6)
        val_cutoff = int(len(dates) * 0.8)
        train_dates = set(dates[:train_cutoff])
        val_dates = set(dates[train_cutoff:val_cutoff])
        test_dates = set(dates[val_cutoff:])

        train_mask = meta["trade_date"].isin(train_dates).to_numpy()
        val_mask = meta["trade_date"].isin(val_dates).to_numpy()
        test_mask = meta["trade_date"].isin(test_dates).to_numpy()

        feature_cols = [str(c) for c in x.columns if c != "symbol"]
        x_train = x.loc[train_mask, feature_cols].astype(float)
        x_val = x.loc[val_mask, feature_cols].astype(float)
        x_test = x.loc[test_mask, feature_cols].astype(float)
        y_train = y.loc[train_mask]
        y_val = y.loc[val_mask]
        y_test = y.loc[test_mask]

        for name, part in (("training", y_train), ("validation", y_val), ("test", y_test)):
            if len(set(part.tolist())) < 2:
                raise ValueError(
                    f"cannot train classifier: {name} split has a single class "
                    f"(labels: {sorted(set(part.tolist()))}). Mixed classes are "
                    "required in every partition — check the data fixture (KI-008)."
                )

        scaler = StandardScaler()
        x_train_s = scaler.fit_transform(x_train)
        x_val_s = scaler.transform(x_val)
        x_test_s = scaler.transform(x_test)

        # XGBoost with modest depth (synthetic data is small)
        model = _make_xgboost(self.random_state)
        model.fit(x_train_s, y_train)

        # Calibrate on validation set (Platt = sigmoid, fast for small data)
        sigmoid = _SigmoidCalibrator().fit(model.predict_proba(x_val_s)[:, 1], y_val)
        calibrator = _CalibratedClassifier(model, sigmoid)

        # Evaluate on test set
        y_pred_proba = calibrator.predict_proba(x_test_s)[:, 1]
        y_pred = calibrator.predict(x_test_s)

        metrics = {
            "roc_auc": float(roc_auc_score(y_test, y_pred_proba)),
            "brier": float(brier_score_loss(y_test, y_pred_proba)),
            "log_loss": float(log_loss(y_test, y_pred_proba)),
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "precision": float(precision_score(y_test, y_pred, zero_division=0)),
            "recall": float(recall_score(y_test, y_pred, zero_division=0)),
            "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        }

        return TrainingResult(
            model=model,
            calibrator=calibrator,
            scaler=scaler,
            feature_columns=[str(c) for c in feature_cols],
            metrics=metrics,
            split_sizes={
                "train": int(train_mask.sum()),
                "val": int(val_mask.sum()),
                "test": int(test_mask.sum()),
            },
        )

    def train_and_register(
        self,
        dataset: Dataset,
        registry: ModelRegistry,
        model_id: str = "price_direction_xgb",
    ) -> ModelEntry:
        """Train, evaluate, and register the model as APPROVED."""
        result = self.train(dataset)
        entry = ModelEntry(
            model_id=model_id,
            version="1.0.0",
            feature_version=FEATURE_VERSION,
            training_data_version=TRAINING_DATA_VERSION,
            target="P(return > 0) over 5TD",
            horizon_days=self.horizon_days,
            model=result.model,
            calibrator=result.calibrator,
            scaler=result.scaler,
            feature_columns=result.feature_columns,
            metrics=result.metrics,
            parameters={"n_estimators": 50, "max_depth": 3, "calibration": "sigmoid"},
            owner="system",
            status="APPROVED",
        )
        registry.register(entry)
        return entry
