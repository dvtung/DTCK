"""Unit tests for the GĐ 3 feature engine (pure functions + look-ahead rule)."""

from __future__ import annotations

from datetime import date

import pytest

from src.quant.strategy.feature_engine import (
    FeatureConfig,
    compute_group_scores,
    load_config,
)
from src.quant.strategy.features import (
    C_CURRENT_ASSETS,
    C_CURRENT_LIABILITIES,
    C_EPS,
    C_EQUITY,
    C_LIABILITIES,
    C_NET_PROFIT,
    C_OPERATING_CF,
    C_REVENUE,
    C_TOTAL_ASSETS,
    FEATURES,
    FeatureSnapshot,
    PeriodValues,
    compute_raw_features,
)


def _quarter(year: int, quarter: int, **values: float) -> PeriodValues:
    month = quarter * 3
    return PeriodValues(
        period_type="QUARTER",
        fiscal_year=year,
        fiscal_period=quarter,
        report_date=date(year, month, {3: 31, 6: 30, 9: 30, 12: 31}[month]),
        values=dict(values),
    )


def _snapshot(**kwargs) -> FeatureSnapshot:
    base = {
        "symbol": "FPT",
        "as_of": date(2026, 10, 3),
        "closes": tuple(100.0 + i for i in range(260)),
        "volumes": tuple(1_000_000.0 for _ in range(260)),
        "values": tuple(50_000_000_000.0 for _ in range(260)),
        "index_closes": tuple(1200.0 + i for i in range(260)),
    }
    base.update(kwargs)
    return FeatureSnapshot(**base)  # type: ignore[arg-type]


def _fundamentals() -> tuple[PeriodValues, ...]:
    quarters = []
    for index, (year, quarter) in enumerate([(2025, 3), (2025, 4), (2026, 1), (2026, 2)]):
        quarters.append(
            _quarter(
                year,
                quarter,
                **{
                    C_REVENUE: 10_000_000_000_000.0 * (1 + 0.05 * index),
                    C_NET_PROFIT: 2_000_000_000_000.0,
                    C_EPS: 1_000.0,
                    C_TOTAL_ASSETS: 60_000_000_000_000.0,
                    C_EQUITY: 30_000_000_000_000.0,
                    C_LIABILITIES: 30_000_000_000_000.0,
                    C_CURRENT_ASSETS: 20_000_000_000_000.0,
                    C_CURRENT_LIABILITIES: 10_000_000_000_000.0,
                    C_OPERATING_CF: 2_500_000_000_000.0,
                },
            )
        )
    return tuple(quarters)


class TestRegistry:
    def test_every_feature_declares_a_known_group(self) -> None:
        from src.quant.strategy.groups import GROUPS

        assert FEATURES, "registry must not be empty"
        for spec in FEATURES:
            assert spec.group in GROUPS

    def test_feature_names_are_unique(self) -> None:
        names = [spec.name for spec in FEATURES]
        assert len(names) == len(set(names))


class TestFeatureValues:
    def test_roe_and_net_margin_from_real_line_items(self) -> None:
        raw = compute_raw_features(_snapshot(financials=_fundamentals()))
        # TTM profit = 4 × 2e12; equity = 3e13 → 0.2667
        assert raw["roe_ttm"] == pytest.approx(4 * 2e12 / 3e13, rel=1e-6)
        # Latest quarter revenue is 10e12 × 1.15 → margin = 2e12 / 11.5e12.
        assert raw["net_margin"] == pytest.approx(2e12 / 11.5e12, rel=1e-6)
        assert raw["cfo_to_net_profit_ttm"] == pytest.approx(1.25, rel=1e-6)

    def test_pe_and_pb_use_ttm_eps(self) -> None:
        snapshot = _snapshot(financials=_fundamentals())
        raw = compute_raw_features(snapshot)
        price = snapshot.closes[-1]
        assert raw["pe_ttm"] == pytest.approx(price / 4000.0, rel=1e-6)
        # shares = TTM profit / TTM EPS = 8e12 / 4000 = 2e9
        # book/share = 3e13 / 2e9 = 15000 → P/B = price / 15000
        assert raw["pb"] == pytest.approx(price / 15_000.0, rel=1e-6)

    def test_technical_features_are_deterministic(self) -> None:
        snapshot = _snapshot(financials=_fundamentals())
        first = compute_raw_features(snapshot)
        second = compute_raw_features(snapshot)
        assert first == second
        assert first["price_vs_sma20"] is not None
        assert first["atr20_pct"] is not None
        assert first["macd_hist_pct"] is not None

    def test_missing_financials_yield_none_not_zero(self) -> None:
        raw = compute_raw_features(_snapshot())
        assert raw["roe_ttm"] is None
        assert raw["pe_ttm"] is None
        assert raw["revenue_yoy"] is None
        # Price-only features still compute.
        assert raw["price_vs_sma20"] is not None


class TestIndustryRules:
    def test_banks_are_excluded_from_generic_leverage_and_pe(self) -> None:
        snapshot = _snapshot(industry="banking", financials=_fundamentals())
        raw = compute_raw_features(snapshot)
        assert raw["debt_to_equity"] is None  # generic D/E is meaningless for banks
        assert raw["current_ratio"] is None
        assert raw["pe_ttm"] is None
        # Industry-agnostic features still apply.
        assert raw["roe_ttm"] is not None

    def test_non_bank_keeps_generic_ratios(self) -> None:
        snapshot = _snapshot(industry="steel", financials=_fundamentals())
        raw = compute_raw_features(snapshot)
        assert raw["debt_to_equity"] == pytest.approx(1.0, rel=1e-6)
        assert raw["current_ratio"] == pytest.approx(2.0, rel=1e-6)

    def test_redflag_free_is_none_when_inputs_are_unchecked(self) -> None:
        """Missing red-flag inputs → None (confidence drops), never a fake 1.0."""
        raw = compute_raw_features(_snapshot())
        assert raw["redflag_free"] is None


class TestGroupScores:
    def test_direction_is_applied_and_none_is_excluded(self) -> None:
        raw_by_symbol = {
            "A": {"roe_ttm": 0.30, "pe_ttm": 5.0},
            "B": {"roe_ttm": 0.10, "pe_ttm": 20.0},
        }
        results = {(r.symbol, r.group): r for r in compute_group_scores(raw_by_symbol)}
        # ROE: higher is better → A > B.
        assert results[("A", "quality")].score > results[("B", "quality")].score
        # P/E: lower is better → A > B even though the raw order is reversed.
        assert results[("A", "valuation")].score > results[("B", "valuation")].score
        assert results[("A", "growth")].score is None  # no growth feature present
        assert "revenue_yoy" in results[("A", "growth")].missing

    def test_group_score_is_bounded_0_100(self) -> None:
        raw_by_symbol = {
            "A": {"price_vs_sma20": 0.10, "return_20d": 0.05},
            "B": {"price_vs_sma20": -0.10, "return_20d": -0.05},
        }
        for result in compute_group_scores(raw_by_symbol):
            if result.score is not None:
                assert 0.0 <= result.score <= 100.0


class TestLookAhead:
    def test_config_loads_with_legal_lags(self) -> None:
        cfg = load_config()
        assert cfg.version == "features_v1.0"
        assert cfg.publication_lag_days["QUARTER"] == 45
        assert cfg.publication_lag_days["YEAR"] == 90
        assert cfg.price_lookback_days > 0

    def test_usable_from_prefers_published_date(self) -> None:
        from src.quant.strategy.feature_engine import _usable_from

        cfg = FeatureConfig(
            version="x",
            publication_lag_days={"QUARTER": 45, "YEAR": 90},
            price_lookback_days=300,
            quarters_ttm=4,
            years_cagr=4,
        )
        # An explicit publication date wins over the legal-lag fallback.
        assert _usable_from(date(2026, 6, 30), date(2026, 7, 20), cfg) == date(2026, 7, 20)
        # No publication date → report_date + the legal lag (the safe direction).
        assert _usable_from(date(2026, 6, 30), None, cfg) == date(2026, 8, 14)
        assert _usable_from(date(2025, 12, 31), None, cfg) == date(2026, 3, 31)
