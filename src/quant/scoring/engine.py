"""Scoring engine: ranking + explainability payloads (spec §12, §43, §44).

Wraps the raw factor-score math in ``src.quant.factors.scoring`` with a layer
that answers **why** a stock ranks where it does:

- per-factor contribution to the overall score (weighted score and % share),
- a ranked universe where every stock carries its own decomposition,
- a decision-output label/confidence consistent with §44.

Everything is pure and deterministic; missing factors are excluded and the
overall score is renormalized over available dimensions (mirrors the data
quality scoring convention).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.quant.factors.scoring import WEIGHTS, compute_overall_score

__all__ = [
    "FactorContribution",
    "ScoreDecomposition",
    "StockRanking",
    "decompose_score",
    "score_universe",
    "build_signal_label",
    "build_confidence",
    "SIGNAL_POSITIVE",
    "SIGNAL_NEGATIVE",
    "SIGNAL_NEUTRAL",
]

SIGNAL_POSITIVE = "POSITIVE"
SIGNAL_NEGATIVE = "NEGATIVE"
SIGNAL_NEUTRAL = "NEUTRAL"


@dataclass(frozen=True)
class FactorContribution:
    """A single factor's share of the overall score.

    ``weighted_score`` is ``score * normalized_weight`` (normalized over the
    available factors only). ``contribution_pct`` is the percentage of the
    overall score that this factor drives, or None when the overall is None.
    """

    factor: str
    score: float
    weight: float
    weighted_score: float
    contribution_pct: float | None


@dataclass(frozen=True)
class ScoreDecomposition:
    """Overall score + the factor decomposition that produced it (§43)."""

    overall_score: float | None
    contributions: list[FactorContribution] = field(default_factory=list)

    def contributing_factors(self) -> list[str]:
        """Names of factors that actually contributed (in descending order)."""
        scored = [c for c in self.contributions if c.score is not None]
        scored.sort(key=lambda c: c.contribution_pct or 0.0, reverse=True)
        return [c.factor for c in scored]


@dataclass(frozen=True)
class StockRanking:
    """One stock's outcome in a scoring run (§44 decision payload)."""

    stock_id: str
    overall_score: float | None
    decomposition: ScoreDecomposition
    signal: str
    confidence: float

    # Multi-factor input scores preserved for drill-down (§43).
    factor_scores: dict[str, float | None] = field(default_factory=dict)


def decompose_score(
    factor_scores: dict[str, float | None],
    weights: dict[str, float] | None = None,
) -> ScoreDecomposition:
    """Decompose an overall score into per-factor contributions (§43).

    ``factor_scores`` uses the dimension keys from WEIGHTS (fundamental,
    technical, momentum, valuation, quality, risk). Missing dimensions are
    excluded and the weights renormalized.
    """
    w = weights or WEIGHTS
    available = {k: v for k, v in factor_scores.items() if v is not None and k in w}
    overall = compute_overall_score(factor_scores, w)

    if not available:
        return ScoreDecomposition(overall_score=None, contributions=[])

    # weight_sum is > 0 whenever available is non-empty (weights are all > 0).
    contributions = [
        FactorContribution(
            factor=k,
            score=v,
            weight=w[k],
            weighted_score=v * w[k],
            contribution_pct=v * w[k] / overall if overall else None,
        )
        for k, v in available.items()
    ]
    contributions.sort(key=lambda c: c.contribution_pct or 0.0, reverse=True)
    return ScoreDecomposition(overall_score=overall, contributions=contributions)


def build_signal_label(score: float | None) -> str:
    """Decision label from an overall score (§44).

    Thresholds: >= 70 → POSITIVE, < 40 → NEGATIVE, else NEUTRAL.
    A None score yields SIGNAL_NEUTRAL.
    """
    if score is None:
        return SIGNAL_NEUTRAL
    if score >= 70.0:
        return SIGNAL_POSITIVE
    if score < 40.0:
        return SIGNAL_NEGATIVE
    return SIGNAL_NEUTRAL


def build_confidence(overall: float | None, n_factors: int) -> float:
    """Heuristic confidence in [0, 1] (§44).

    Scales with overall-score extremity and with how many factors were
    available (more evidence → higher confidence). Pure and deterministic.
    """
    if overall is None or n_factors <= 0:
        return 0.0
    extremity = abs(overall - 55.0) / 45.0  # 0 near 55, ~1 at 0 or 100
    coverage = min(float(n_factors) / len(WEIGHTS), 1.0)
    confidence = 0.5 * max(extremity, 0.0) + 0.5 * coverage
    return round(max(0.0, min(1.0, confidence)), 4)


def score_universe(
    universe_scores: dict[str, dict[str, float | None]],
    weights: dict[str, float] | None = None,
) -> list[StockRanking]:
    """Score and rank an entire universe, each entry with an explainability payload.

    ``universe_scores`` maps stock_id → {factor: score-or-None}. Returns a list
    of StockRanking ordered by overall score (descending); stocks with no
    available factors are placed at the end.
    """
    rankings: list[StockRanking] = []
    for stock_id, factor_scores in universe_scores.items():
        decomposition = decompose_score(factor_scores, weights)
        ranking = StockRanking(
            stock_id=stock_id,
            overall_score=decomposition.overall_score,
            decomposition=decomposition,
            signal=build_signal_label(decomposition.overall_score),
            confidence=build_confidence(
                decomposition.overall_score,
                len(decomposition.contributions),
            ),
            factor_scores=dict(factor_scores),
        )
        rankings.append(ranking)

    rankings.sort(
        key=lambda r: (
            r.overall_score is not None,  # None scores last
            r.overall_score if r.overall_score is not None else -1.0,
        ),
        reverse=True,
    )
    return rankings
