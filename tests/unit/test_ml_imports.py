import subprocess
import sys
import textwrap
from pathlib import Path

from src.ml import ModelTrainer, PredictionService
from src.ml.training import ModelTrainer as PackageModelTrainer
from src.ml.training import TrainingResult


def test_ml_training_symbols_are_importable() -> None:
    assert ModelTrainer is PackageModelTrainer
    assert TrainingResult.__name__ == "TrainingResult"
    assert PredictionService.__name__ == "PredictionService"


def test_api_import_without_optional_ml_dependencies() -> None:
    script = textwrap.dedent('''
        import importlib.abc
        import sys

        class BlockML(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split(".")[0] in {"sklearn", "xgboost", "lightgbm"}:
                    raise ModuleNotFoundError(fullname, name=fullname)
                return None

        sys.meta_path.insert(0, BlockML())
        import apps.api.main
        import src.ml
        from src.ml import FeatureDatasetBuilder, PredictionService
        assert "src.ml.training" not in sys.modules
        assert FeatureDatasetBuilder.__name__ == "FeatureDatasetBuilder"
        assert PredictionService.__name__ == "PredictionService"
        try:
            src.ml.ModelTrainer
        except ModuleNotFoundError as exc:
            assert exc.name == "sklearn"
        else:
            raise AssertionError("training must require sklearn")
    ''')
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_ml_unknown_export_raises_attribute_error() -> None:
    import pytest

    import src.ml

    with pytest.raises(AttributeError, match="has no attribute"):
        _ = src.ml.unknown_export
    assert "ModelTrainer" in dir(src.ml)
