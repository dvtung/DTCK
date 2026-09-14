"""T007 tests (part 2): risk indicators + factor scoring."""

from __future__ import annotations

import math

from src.market.risk import risk
from src.quant.factors import scoring


class TestRisk:
    def test_max_drawdown(self) -> None:
        result = risk.max_drawdown([100.0, 120.0, 90.0, 110.0])
        assert result[0] is None
        assert result[1] == 0.0
        assert result[2] is not None and abs(result[2] - (-0.25)) < 1e-9
        assert result[3] is not None and abs(result[3] - (-0.25)) < 1e-9

    def test_volatility_shape(self) -> None:
        close = [100.0 + i for i in range(30)]
        result = risk.volatility(close, period=20)
        assert len(result) == 30
        assert all(v is None for v in result[:20])
        assert all(v is not None and v >= 0 for v in result[20:])
        assert all(not math.isnan(v) for v in result[20:] if v is not None)

    def test_beta_perfect(self) -> None:
        rets = [0.1, 0.2, 0.3, 0.4]
        result = risk.beta(rets, rets, period=4)
        assert result[:3] == [None, None, None]
        assert result[3] is not None and abs(result[3] - 1.0) < 1e-9

    def test_misc(self) -> None:
        assert risk.liquidity(1e9, 5e8) == 2.0
        assert risk.liquidity(1e9, 0.0) is None
        assert risk.debt_risk(0.3) == 0.0
        assert risk.debt_risk(0.7) == 0.33
        assert risk.debt_risk(1.5) == 0.67
        assert risk.debt_risk(3.0) == 1.0

    def test_gap_risk_flat(self) -> None:
        close = [100.0] * 5
        open_ = [100.0] * 5
        result = risk.gap_risk(close, open_, period=2)
        assert result[0] is None
        assert result[1] is None
        assert all(v == 0.0 for v in result[2:])


class TestScoring:
    def test_overall_weighted(self) -> None:
        scores: dict[str, float | None] = {
            "fundamental": 80.0,
            "technical": 60.0,
            "momentum": 40.0,
            "valuation": 20.0,
            "quality": 100.0,
            "risk": 0.0,
        }
        expected = 0.30 * 80 + 0.20 * 60 + 0.15 * 40 + 0.15 * 20 + 0.10 * 100
        assert scoring.compute_overall_score(scores) == expected

    def test_overall_renormalized(self) -> None:
        scores: dict[str, float | None] = {
            "fundamental": 100.0,
            "technical": None,
            "momentum": None,
            "valuation": None,
            "quality": None,
            "risk": None,
        }
        assert scoring.compute_overall_score(scores) == 100.0

    def test_overall_none(self) -> None:
        scores = {k: None for k in scoring.WEIGHTS}
        assert scoring.compute_overall_score(scores) is None

    def test_factor_and_rank(self) -> None:
        out = scoring.compute_factor_scores(
            {"fundamental": 5.0},
            {"fundamental": [1.0, 2.0, 3.0, 4.0, 6.0]},
        )
        assert out["fundamental"] == 80.0
        assert out["technical"] is None
        ranked = scoring.rank_stocks({"a": 10.0, "b": None, "c": 30.0})
        assert ranked[0] == ("c", 30.0)
        assert ranked[2] == ("b", 0.0)
