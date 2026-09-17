"""T008 tests — scoring engine: decomposition, ranking, decision payloads (§12/§43/§44)."""

from __future__ import annotations

from src.quant.scoring.engine import (
    SIGNAL_NEGATIVE,
    SIGNAL_NEUTRAL,
    SIGNAL_POSITIVE,
    ScoreDecomposition,
    StockRanking,
    build_confidence,
    build_signal_label,
    decompose_score,
    score_universe,
)


def _full_scores() -> dict[str, float | None]:
    return {
        "fundamental": 80.0,
        "technical": 60.0,
        "momentum": 40.0,
        "valuation": 20.0,
        "quality": 100.0,
        "risk": 0.0,
    }


class TestDecompose:
    def test_contributions_sum_to_overall(self) -> None:
        dec = decompose_score(_full_scores())
        assert dec.overall_score is not None
        assert len(dec.contributions) == 6
        weighted_sum = sum(c.weighted_score for c in dec.contributions)
        # renormalized over available factors (all 6 present → weights sum to 1)
        assert abs(weighted_sum - dec.overall_score) < 1e-9
        # contribution shares must add up to 1 when all 6 dimensions exist
        assert abs(sum(c.contribution_pct or 0.0 for c in dec.contributions) - 1.0) < 1e-9

    def test_renormalization_excludes_missing(self) -> None:
        scores = _full_scores()
        scores["technical"] = None
        scores["what_ever_unknown"] = 999.0  # ignored (not in weights)
        dec = decompose_score(scores)
        assert dec.overall_score is not None
        assert all(c.factor != "technical" for c in dec.contributions)
        assert all(c.factor != "what_ever_unknown" for c in dec.contributions)

    def test_contributions_sorted_by_share(self) -> None:
        dec = decompose_score(_full_scores())
        pcts = [c.contribution_pct for c in dec.contributions]
        # all present, all percentages non-None
        assert all(p is not None for p in pcts)
        assert pcts == sorted(pcts, reverse=True)

    def test_empty_returns_none(self) -> None:
        dec = decompose_score({k: None for k in ["fundamental", "technical"]})
        assert dec.overall_score is None
        assert dec.contributions == []

    def test_single_factor_renormalizes_to_full_weight(self) -> None:
        """One available factor drives 100% of the score (weight 1.0, share 1.0)."""
        scores = {"fundamental": 100.0}
        dec = decompose_score(scores)
        assert len(dec.contributions) == 1
        contribution = dec.contributions[0]
        assert contribution.weight == 1.0  # renormalized from baseline 0.30
        assert contribution.weighted_score == 100.0
        assert contribution.contribution_pct == 1.0
        assert dec.overall_score == 100.0  # renormalized single-dimension

    def test_weights_are_renormalized_over_available_factors(self) -> None:
        """Σ weighted_score == overall and Σ contribution_pct == 1 even when
        factors are missing (the overall score itself is renormalized)."""
        scores = {k: None for k in _full_scores()}
        scores["fundamental"] = 80.0
        scores["valuation"] = 40.0
        dec = decompose_score(scores)
        assert dec.overall_score is not None
        weight_sum = sum(c.weight for c in dec.contributions)
        assert abs(weight_sum - 1.0) < 1e-12  # stored weights sum to 1
        weighted_sum = sum(c.weighted_score for c in dec.contributions)
        assert abs(weighted_sum - dec.overall_score) < 1e-9
        pct_sum = sum(c.contribution_pct or 0.0 for c in dec.contributions)
        assert abs(pct_sum - 1.0) < 1e-9


class TestBuildPayloads:
    def test_signal_labels(self) -> None:
        assert build_signal_label(100.0) == SIGNAL_POSITIVE
        assert build_signal_label(70.0) == SIGNAL_POSITIVE
        assert build_signal_label(55.0) == SIGNAL_NEUTRAL
        assert build_signal_label(39.0) == SIGNAL_NEGATIVE
        assert build_signal_label(None) == SIGNAL_NEUTRAL

    def test_confidence_bounds(self) -> None:
        assert build_confidence(None, 1) == 0.0
        assert build_confidence(80.0, 0) == 0.0
        c = build_confidence(100.0, 6)
        assert 0.0 <= c <= 1.0
        c_low = build_confidence(55.0, 6)
        assert c_low <= 0.5  # neutral score → low confidence from extremity term

    def test_confidence_more_factors_more_confident(self) -> None:
        c1 = build_confidence(90.0, 1)
        c6 = build_confidence(90.0, 6)
        assert c6 >= c1


class TestScoreUniverse:
    def test_rank_order_and_none_last(self) -> None:
        universe = {
            "a": {"fundamental": 100.0},
            "b": {k: 50.0 for k in ["fundamental", "technical", "momentum"]},
            "c": {"fundamental": None, "technical": None},
        }
        ranked = score_universe(universe)
        assert [r.stock_id for r in ranked] == ["a", "b", "c"]
        assert ranked[-1].overall_score is None

    def test_each_ranking_explains(self) -> None:
        universe = {"FPT": _full_scores(), "VCB": {"fundamental": 90.0}}
        ranked = score_universe(universe)
        for r in ranked:
            assert isinstance(r, StockRanking)
            assert isinstance(r.decomposition, ScoreDecomposition)
            if r.overall_score is not None:
                assert r.signal in (SIGNAL_POSITIVE, SIGNAL_NEGATIVE, SIGNAL_NEUTRAL)
                assert 0.0 <= r.confidence <= 1.0

    def test_deterministic(self) -> None:
        universe = {"FPT": _full_scores(), "VCB": {"fundamental": 90.0}}
        assert score_universe(universe) == score_universe(universe)
