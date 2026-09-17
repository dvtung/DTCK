"""Feature dataset builder for ML prediction (spec §14.3, ML_ARCHITECTURE.md §2/§3).

Extracts deterministic features from the MarketService + quant engine at each
trade date, with strict as-of alignment (§6/§17) — no future data leaks.
Builds forward-return targets over a declared horizon for both classification
(P(return > 0)) and regression (expected return).
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass
from datetime import date
from typing import Protocol, cast

import pandas as pd

from src.market.risk import risk as risk_engine
from src.market.technical import indicators as tech

__all__ = [
    "FeatureDatasetBuilder",
    "Dataset",
    "MarketLike",
    "FEATURE_VERSION",
    "DEFAULT_HORIZON_DAYS",
]

FEATURE_VERSION = "feature_v1"
DEFAULT_HORIZON_DAYS = 5


class MarketLike(Protocol):
    """Minimal market-service surface consumed by the ML layer + agent tools (KI-008).

    ``apps.api.services.market_data.MarketService`` is the reference
    implementation; tests may substitute narrower deterministic stubs.
    """

    def list_stocks(
        self, exchange: str | None, sector: str | None, vn30: bool | None
    ) -> list[dict[str, object]]: ...

    def get_regime(self) -> dict[str, object]: ...
    def get_stock(self, symbol: str) -> dict[str, object] | None: ...
    def get_prices(self, symbol: str) -> list[dict[str, object]] | None: ...
    def get_ranking(self, symbol: str) -> dict[str, object] | None: ...
    def get_indicators(self, symbol: str) -> dict[str, object] | None: ...
    def get_valuation_summary(self, symbol: str) -> dict[str, object] | None: ...
    def get_quality(self, symbol: str) -> dict[str, object] | None: ...
    def list_news(self) -> list[dict[str, object]]: ...


@dataclass(frozen=True)
class Dataset:
    """A ready-to-train dataset with as-of-aligned features and targets.

    Each row corresponds to one (stock, trade_date) sample.  ``features``
    contains only data known at that date; ``target_return`` is the realized
    forward return over ``horizon_days``; ``target_positive`` is the binary
    label P(return > 0).
    """

    features: pd.DataFrame
    target_return: pd.Series
    target_positive: pd.Series
    metadata: pd.DataFrame  # columns: symbol, trade_date, horizon_days, feature_version


class FeatureDatasetBuilder:
    """Build a feature matrix + targets from MarketService price data.

    As-of alignment: features at date T use only prices up to and including T.
    The forward target spans T -> T + horizon_days.  Samples without a full
    horizon are dropped (no look-ahead, no padding).
    """

    REGIME_MAP: dict[str, int] = {"BULL": 0, "SIDEWAYS": 1, "VOLATILE": 2, "BEAR": 3}

    def __init__(self, horizon_days: int = DEFAULT_HORIZON_DAYS) -> None:
        self.horizon_days = horizon_days

    def build(
        self,
        market: MarketLike,
        symbols: list[str] | None = None,
    ) -> Dataset:
        """Build dataset from a MarketService-like object."""
        if symbols is None:
            symbols = [
                str(s["symbol"])
                for s in market.list_stocks(None, None, None)
            ]

        regime = market.get_regime()
        regime_code = self.REGIME_MAP.get(str(regime.get("regime", "BULL")), 0)

        rows: list[dict[str, float]] = []
        metas: list[dict[str, object]] = []
        targets_return: list[float] = []
        targets_positive: list[int] = []

        for sym in symbols:
            prices = market.get_prices(sym)
            if not prices or len(prices) < 30:
                continue
            closes = [float(str(r["close"])) for r in prices]
            volumes = [int(float(str(r["volume"]))) for r in prices]
            dates = [cast(date, r["trade_date"]) for r in prices]

            ranking = market.get_ranking(sym)
            score = ranking.get("overall_score") if ranking else None
            rank = float(score) if isinstance(score, (int, float)) else 0.0
            signal_map = {"POSITIVE": 1.0, "NEUTRAL": 0.0, "NEGATIVE": -1.0}
            default_signal = "NEUTRAL"
            raw_signal = str(ranking.get("signal", default_signal)) if ranking else default_signal
            signal_val = signal_map.get(raw_signal, 0.0)

            for i in range(20, len(dates) - self.horizon_days):
                window_close = closes[: i + 1]
                window_vol = volumes[: i + 1]
                feature = self._features_at(sym, window_close, window_vol, dates[i], regime_code)
                feature["overall_score"] = round(rank, 4)
                feature["signal_encoded"] = signal_val
                rows.append(feature)

                fwd = self._fwd_return(closes, i, self.horizon_days)
                targets_return.append(round(fwd, 6))
                targets_positive.append(1 if fwd > 0 else 0)
                metas.append(
                    {
                        "symbol": sym,
                        "trade_date": dates[i],
                        "horizon_days": self.horizon_days,
                        "feature_version": FEATURE_VERSION,
                    }
                )

        features_df = pd.DataFrame(rows)
        meta_df = pd.DataFrame(metas)
        return Dataset(
            features=features_df,
            target_return=pd.Series(targets_return, name="target_return"),
            target_positive=pd.Series(targets_positive, name="target_positive"),
            metadata=meta_df,
        )

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _fwd_return(closes: list[float], i: int, horizon: int) -> float:
        """Forward return from day i to day i+horizon (no leakage)."""
        if i + horizon >= len(closes):
            return float("nan")
        return (closes[i + horizon] - closes[i]) / closes[i]

    @staticmethod
    def _series_at(values: list[float | None], i: int) -> float | None:
        """Last non-None value at or before index i."""
        for j in range(i, -1, -1):
            v = values[j] if j < len(values) else None
            if v is not None:
                return float(v)
        return None

    def _features_at(
        self,
        symbol: str,
        closes: list[float],
        volumes: list[int],
        trade_date: date,
        regime_code: int,
    ) -> dict[str, float]:
        """Extract all features known at the close of ``trade_date``."""
        i = len(closes) - 1
        result: dict[str, float] = {
            # Process-stable symbol encoding (PYTHONHASHSEED-independent, §7).
            "symbol": float(zlib.crc32(symbol.encode("utf-8")) % 1_000_000),
            "trade_date_ord": float(trade_date.toordinal()),
            "regime_encoded": float(regime_code),
            "close": round(closes[i], 4),
            "close_lag1": round(closes[i - 1], 4) if i >= 1 else 0.0,
        }

        # Return features
        for period, key in [(1, "ret_1d"), (5, "ret_5d"), (10, "ret_10d"), (20, "ret_20d")]:
            if i >= period:
                result[key] = round((closes[i] - closes[i - period]) / closes[i - period], 6)
            else:
                result[key] = 0.0

        # Technical indicators
        sma20 = tech.sma(closes, 20)
        ema12 = tech.ema(closes, 12)
        rsi14 = tech.rsi(closes, 14)
        result["sma20"] = round(self._series_at(sma20, i) or 0.0, 4)
        result["ema12"] = round(self._series_at(ema12, i) or 0.0, 4)
        result["rsi14"] = round(self._series_at(rsi14, i) or 0.0, 4)
        if result["sma20"] > 0:
            result["price_vs_sma20"] = round(closes[i] / result["sma20"], 4)
        else:
            result["price_vs_sma20"] = 1.0

        # Risk metrics
        vols = risk_engine.volatility(closes, period=20)
        drawdowns = risk_engine.max_drawdown(closes)
        result["volatility_20d"] = round(self._series_at(vols, i) or 0.0, 6)
        result["max_drawdown_20d"] = round(abs(self._series_at(drawdowns, i) or 0.0), 6)

        # Volume features
        result["volume"] = float(volumes[i])
        vol_window = volumes[max(0, i - 19) : i + 1]
        result["volume_avg_20"] = round(sum(vol_window) / len(vol_window), 2) if vol_window else 0.0
        if result["volume_avg_20"] > 0:
            result["volume_vs_avg"] = round(result["volume"] / result["volume_avg_20"], 4)
        else:
            result["volume_vs_avg"] = 1.0

        # Price range features
        if i >= 20:
            hi = max(closes[i - 20 : i + 1])
            lo = min(closes[i - 20 : i + 1])
            result["price_range_20d"] = round((hi - lo) / lo, 6) if lo > 0 else 0.0
        else:
            result["price_range_20d"] = 0.0

        return result
