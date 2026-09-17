"""ML feature dataset, training, calibration, model registry, prediction (T014).

Deterministic, scikit-learn/xgboost-based. Models are trained offline and
served in-process by the Predictor. See docs/ML_ARCHITECTURE.md.

Import hygiene: the TRAINING stack (``training`` → scikit-learn) is imported
LAZILY via PEP 562 ``__getattr__``. The serving layer (feature dataset, model
registry, predictor) must stay importable without the optional ``[ml]`` extra
so the API can boot and serve fallback predictions offline; training raises a
clear error only when actually used without scikit-learn installed.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # static-analysis view of the full package (ruff: refs live in _EXPORTS)
    from src.ml.feature_dataset import Dataset, FeatureDatasetBuilder  # noqa: F401
    from src.ml.model_registry import (  # noqa: F401
        ModelEntry,
        ModelRegistry,
        get_default_registry,
    )
    from src.ml.predictor import Prediction, PredictionService  # noqa: F401
    from src.ml.training import (  # noqa: F401
        TRAINING_DATA_VERSION,
        ModelTrainer,
        TrainingResult,
    )

# name -> module providing it (imported on first attribute access)
_EXPORTS: dict[str, str] = {
    "FeatureDatasetBuilder": "src.ml.feature_dataset",
    "Dataset": "src.ml.feature_dataset",
    "FEATURE_VERSION": "src.ml.feature_dataset",
    "DEFAULT_HORIZON_DAYS": "src.ml.feature_dataset",
    "ModelEntry": "src.ml.model_registry",
    "ModelRegistry": "src.ml.model_registry",
    "get_default_registry": "src.ml.model_registry",
    "Prediction": "src.ml.predictor",
    "PredictionService": "src.ml.predictor",
    "ModelTrainer": "src.ml.training",
    "TrainingResult": "src.ml.training",
    "TRAINING_DATA_VERSION": "src.ml.training",
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:  # PEP 562 module-level lazy attribute
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    module = importlib.import_module(module_name)
    return getattr(module, name)


def __dir__() -> list[str]:
    return sorted(__all__)
