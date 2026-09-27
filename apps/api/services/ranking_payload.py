"""Ranking payload shaping shared by the in-memory and DB market sources (W1).

The explainability payload of ``GET /api/v1/stocks/ranked`` (§43/§44) is part of
the API contract, so its shaping lives in exactly one place and both sources use
it — a ranking computed from the database is indistinguishable in shape from one
computed over the in-memory fixture.
"""

from __future__ import annotations

from typing import Any

from src.quant.scoring.engine import StockRanking


def to_ranking_payload(ranking: StockRanking, rank: int, total: int) -> dict[str, Any]:
    """Serialize one ``StockRanking`` into the ``RankingOut`` payload shape.

    ``contribution_pct`` is a share vector that sums to 1 before rounding;
    rounding each component independently could leave 0.9999 (a live finding —
    worst deviation 1e-4 across the ranked universe), so the residual is
    folded into the largest component after rounding.  Only applied when the
    *unrounded* shares genuinely sum to 1, so partial vectors are untouched.
    """
    contributions = ranking.decomposition.contributions

    rounded_pct = [
        round(c.contribution_pct, 4) if c.contribution_pct is not None else None
        for c in contributions
    ]
    raw = [c.contribution_pct for c in contributions]
    if all(v is not None for v in raw):
        raw_sum = sum(v for v in raw if v is not None)
        rounded_sum = sum(v for v in rounded_pct if v is not None)
        if abs(raw_sum - 1.0) < 1e-9 and rounded_sum != 1.0:
            # Fold the rounding residual into the largest share (deterministic).
            valid_indices = [i for i, v in enumerate(rounded_pct) if v is not None]

            def _sort_key(idx: int) -> float:
                val = rounded_pct[idx]
                return float(val) if val is not None else float("-inf")

            largest = max(valid_indices, key=_sort_key)
            residual = round(1.0 - rounded_sum, 4)
            current = rounded_pct[largest]
            rounded_pct[largest] = round((current if current is not None else 0.0) + residual, 4)

    return {
        "symbol": ranking.stock_id,
        "overall_score": (
            round(ranking.overall_score, 2) if ranking.overall_score is not None else None
        ),
        "signal": ranking.signal,
        "confidence": ranking.confidence,
        "rank": rank,
        "total": total,
        "contributions": [
            {
                "factor": c.factor,
                "score": c.score,
                "weight": c.weight,
                "weighted_score": round(c.weighted_score, 4),
                "contribution_pct": rounded_pct[i],
            }
            for i, c in enumerate(contributions)
        ],
    }


__all__ = ["to_ranking_payload"]
