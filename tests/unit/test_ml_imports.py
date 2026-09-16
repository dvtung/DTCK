from src.ml import ModelTrainer, PredictionService
from src.ml.training import ModelTrainer as PackageModelTrainer
from src.ml.training import TrainingResult


def test_ml_training_symbols_are_importable() -> None:
    assert ModelTrainer is PackageModelTrainer
    assert TrainingResult.__name__ == "TrainingResult"
    assert PredictionService.__name__ == "PredictionService"
