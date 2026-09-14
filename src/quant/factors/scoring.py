"""Factor score aggregation (spec §12, QUANT_ENGINE.md §3).

Combines raw factor values into 6 dimension scores (0-100) using percentile
ranks within the universe, then computes the overall composite score using
baseline weights.

The baseline weights are assumptions to be validated/re-learned via
backtesting (§12 warning) — never assumed optimal.
"""

from __future__ import annotations

# Baseline scoring weights (spec §12)
WEIGHTS: dict[str, float] = {
    "fundamental": 0.30,
    "technical": 0.20,
    "momentum": 0.15,
    "valuation": 0.15,
    "quality": 0.10,
    "risk": 0.10,
}

DEFAULT_SCORING_VERSION = "baseline_1.0"


def percentile_rank(value: float, distribution: list[float]) -> float:
    """Percentile rank of ``value`` within ``distribution`` (0-100).

    Uses the "strictly less than" definition. Returns 0 for empty distribution.
    """
    if not distribution:
        return 0.0
    below = sum(1 for x in distribution if x < value)
    return (below / len(distribution)) * 100


def compute_factor_scores(
    stock_values: dict[str, float],
    universe_values: dict[str, list[float]],
) -> dict[str, float | None]:
    """Compute 6 factor scores for a single stock.

    ``stock_values`` maps factor name → raw value for this stock.
    ``universe_values`` maps factor name → list of raw values for all stocks.

    Returns a dict mapping factor name → score (0-100) or None.
    """
    scores: dict[str, float | None] = {}
    for factor in WEIGHTS:
        value = stock_values.get(factor)
        distribution = universe_values.get(factor, [])
        if value is None or not distribution:
            scores[factor] = None
        else:
            scores[factor] = percentile_rank(value, distribution)
    return scores


def compute_overall_score(
    factor_scores: dict[str, float | None],
    weights: dict[str, float] | None = None,
) -> float | None:
    """Compute overall composite score from factor scores.

    Missing factor scores are excluded and the remaining weights are
    renormalized (same approach as data quality scoring).

    Returns ``None`` if no factor scores are available.
    """
    w = weights or WEIGHTS
    available = {k: v for k, v in factor_scores.items() if v is not None and k in w}
    if not available:
        return None

    weight_sum = sum(w[k] for k in available)
    if weight_sum <= 0:
        return None

    weighted = sum(w[k] * v for k, v in available.items())
    return weighted / weight_sum


def rank_stocks(
    stock_scores: dict[str, float | None],
) -> list[tuple[str, float]]:
    """Rank stocks by overall score (descending).

    Returns a list of (stock_id, score) tuples, sorted by score descending.
    Stocks with None scores are placed at the end.
    """
    scored = [(sid, score) for sid, score in stock_scores.items() if score is not None]
    scored.sort(key=lambda x: x[1], reverse=True)
    none_scored = [(sid, 0.0) for sid, score in stock_scores.items() if score is None]
    return scored + none_scored


__all__ = [
    "WEIGHTS",
    "DEFAULT_SCORING_VERSION",
    "percentile_rank",
    "compute_factor_scores",
    "compute_overall_score",
    "rank_stocks",
]
