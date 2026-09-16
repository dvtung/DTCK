"""T014 leakage tests — features must never contain forward-looking data (§17).

Regression tests for target leakage: forward returns were previously written
into the feature matrix (``horizon_return_*``), so the training matrix
contained the realized value the target is computed from.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from src.ml.feature_dataset import DEFAULT_HORIZON_DAYS, FeatureDatasetBuilder

N_DAYS = 60


def _market(closes: list[float]):  # noqa: ANN202 - test stub
    """Deterministic market stub exposing the builder's service surface."""

    dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(len(closes))]
    prices = [
        {"trade_date": d, "close": c, "volume": 1_000 + i}
        for i, (d, c) in enumerate(zip(dates, closes, strict=True))
    ]

    class _Market:
        def list_stocks(self, exchange, sector, vn30):
            return [{"symbol": "TEST"}]

        def get_regime(self):
            return {"regime": "BULL", "confidence": 1.0, "trade_date": dates[-1]}

        def get_prices(self, symbol):
            return prices if symbol == "TEST" else None

        def get_ranking(self, symbol):
            return {"overall_score": 0.55, "signal": "POSITIVE"}

    return _Market(), dates


def _closes() -> list[float]:
    return [100.0 + ((i * 7) % 23) - 11 + i * 0.1 for i in range(N_DAYS)]


def test_features_contain_no_forward_return_columns() -> None:
    market, _ = _market(_closes())
    ds = FeatureDatasetBuilder().build(market, symbols=["TEST"])
    leaked = [c for c in ds.features.columns if c.startswith("horizon_return")]
    assert leaked == []


def test_target_is_the_only_forward_looking_field() -> None:
    market, _ = _market(_closes())
    ds = FeatureDatasetBuilder().build(market, symbols=["TEST"])
    # Rows exist and every feature column is computable from data at its date.
    assert len(ds.features) == N_DAYS - 20 - DEFAULT_HORIZON_DAYS
    assert "target_return" not in ds.features.columns


def test_features_invariant_to_future_price_changes() -> None:
    closes = _closes()
    j = len(closes) - 3  # a future date for every earlier feature row
    shocked = list(closes)
    shocked[j] = shocked[j] * 3.0

    market_a, dates = _market(closes)
    market_b, _ = _market(shocked)
    ds_a = FeatureDatasetBuilder().build(market_a, symbols=["TEST"])
    ds_b = FeatureDatasetBuilder().build(market_b, symbols=["TEST"])

    past = (ds_a.metadata["trade_date"] < dates[j]).to_numpy()
    fa = ds_a.features.loc[past].reset_index(drop=True)
    fb = ds_b.features.loc[past].reset_index(drop=True)
    pd.testing.assert_frame_equal(fa, fb)


def test_target_reflects_changed_future_price() -> None:
    closes = _closes()
    j = len(closes) - 3
    shocked = list(closes)
    shocked[j] = shocked[j] * 3.0

    market_a, dates = _market(closes)
    market_b, _ = _market(shocked)
    ds_a = FeatureDatasetBuilder().build(market_a, symbols=["TEST"])
    ds_b = FeatureDatasetBuilder().build(market_b, symbols=["TEST"])

    i = j - DEFAULT_HORIZON_DAYS  # sample whose horizon lands on date j
    row = ds_a.metadata.index[ds_a.metadata["trade_date"] == dates[i]][0]
    assert ds_a.target_return.iloc[row] != ds_b.target_return.iloc[row]


def test_symbol_feature_is_process_stable() -> None:
    code = (
        "from datetime import date\n"
        "from src.ml.feature_dataset import FeatureDatasetBuilder\n"
        "f = FeatureDatasetBuilder()._features_at("
        "'FPT', [100.0] * 30, [1000] * 30, date(2026, 1, 1), 0)\n"
        "print(f['symbol'])\n"
    )
    repo = Path(__file__).resolve().parents[2]
    outs = []
    for seed in ("1", "2"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo,
            env=env,
        )
        outs.append(proc.stdout.strip())
    assert outs[0] == outs[1]
