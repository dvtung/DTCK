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
    """Serialize one ``StockRanking`` into the ``RankingOut`` payload shape."""
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
                "contribution_pct": (
                    round(c.contribution_pct, 4) if c.contribution_pct is not None else None
                ),
            }
            for c in ranking.decomposition.contributions
        ],
    }


__all__ = ["to_ranking_payload"]
