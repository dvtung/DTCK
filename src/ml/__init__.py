"""ML feature dataset, training, calibration, model registry, prediction (T014).

Deterministic, scikit-learn/xgboost-based. Models are trained offline and
served in-process by the Predictor. See docs/ML_ARCHITECTURE.md.
"""

from src.ml.feature_dataset import FeatureDatasetBuilder
from src.ml.model_registry import ModelEntry, ModelRegistry
from src.ml.predictor import Prediction, PredictionService
from src.ml.training import ModelTrainer, TrainingResult

__all__ = [
    "FeatureDatasetBuilder",
    "ModelEntry",
    "ModelRegistry",
    "ModelTrainer",
    "Prediction",
    "PredictionService",
    "TrainingResult",
]
