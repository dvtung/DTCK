"""Exercise real fitting, calibration, and temporal training boundaries."""

from dataclasses import replace
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from src.ml.feature_dataset import Dataset
from src.ml.training import ModelTrainer


def mixed_dataset() -> Dataset:
    """Two symbols per date; both classes in every chronological partition."""
    dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(103)]
    labels = [i % 2 for i in range(206)]
    return Dataset(
        features=pd.DataFrame({
            "symbol": [float(i % 2) for i in range(206)],
            "close": [100.0 + (i % 7) for i in range(206)],
            "ret_1d": [0.01 if label else -0.01 for label in labels],
        }),
        target_return=pd.Series([0.02 if label else -0.02 for label in labels]),
        target_positive=pd.Series(labels),
        metadata=pd.DataFrame({
            "trade_date": [day for day in dates for _ in range(2)],
            "symbol": ["A", "B"] * 103,
            "horizon_days": [5] * 206,
        }),
    )


def test_real_training_calibration_and_date_partitions() -> None:
    dataset = mixed_dataset()
    result = ModelTrainer().train(dataset)
    # Unique dates, not row counts, determine the 60/20/20 boundaries.
    assert result.split_sizes == {"train": 122, "val": 42, "test": 42}
    assert sum(result.split_sizes.values()) == len(dataset.features)
    assert result.feature_columns == ["close", "ret_1d"]
    frame = dataset.features[result.feature_columns].iloc[-10:]
    scaled = result.scaler.transform(frame)
    probabilities = result.calibrator.predict_proba(scaled)
    assert probabilities.shape == (10, 2)
    assert np.isfinite(probabilities).all()
    assert ((probabilities >= 0) & (probabilities <= 1)).all()
    np.testing.assert_allclose(probabilities.sum(axis=1), 1.0)
    assert all(np.isfinite(value) for value in result.metrics.values())
    assert 0 <= result.metrics["roc_auc"] <= 1
    # Scaler statistics must only reflect the training partition.
    np.testing.assert_allclose(
        result.scaler.mean_, dataset.features[result.feature_columns].iloc[:122].mean()
    )


@pytest.mark.parametrize("partition, start, end", [
    ("training", 0, 122), ("validation", 122, 164), ("test", 164, 206),
])
def test_single_class_partition_is_rejected(partition: str, start: int, end: int) -> None:
    dataset = mixed_dataset()
    dataset.target_positive.iloc[start:end] = 1
    with pytest.raises(ValueError, match=f"{partition} split.*single class"):
        ModelTrainer().train(dataset)


def test_regression_target_cannot_be_silently_cast_to_binary_labels() -> None:
    with pytest.raises(ValueError, match="target_positive"):
        ModelTrainer().train(mixed_dataset(), target_col="target_return")


def test_empty_dataset_has_actionable_error() -> None:
    dataset = mixed_dataset()
    empty = replace(
        dataset, features=dataset.features.iloc[:0], metadata=dataset.metadata.iloc[:0],
        target_positive=dataset.target_positive.iloc[:0],
        target_return=dataset.target_return.iloc[:0],
    )
    with pytest.raises(ValueError, match="at least.*dates"):
        ModelTrainer().train(empty)


def test_misaligned_dataset_rejected() -> None:
    dataset = mixed_dataset()
    with pytest.raises(ValueError, match="same number of rows"):
        ModelTrainer().train(replace(dataset, target_positive=dataset.target_positive.iloc[:-1]))


def test_invalid_binary_labels_rejected() -> None:
    dataset = mixed_dataset()
    invalid = replace(dataset, target_positive=pd.Series([2] * 206))
    with pytest.raises(ValueError, match="labels must be"):
        ModelTrainer().train(invalid)
