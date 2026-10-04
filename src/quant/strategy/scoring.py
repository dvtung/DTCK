"""Multi-profile score aggregation: 7 groups -> overall 0-100 + confidence.

Pure and deterministic (ADR-001). Missing groups are excluded and the weights
renormalized over the remaining groups — the documented §12 behaviour, shared
with ``src/quant/scoring/engine.py::decompose_score``. No group value is ever
invented: ``None`` stays ``None``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.quant.strategy.config import weights_for
from src.quant.strategy.groups import GROUPS

__all__ = ["GroupContribution", "ProfileScore", "score_profile"]


@dataclass(frozen=True)
class GroupContribution:
    """One group's share of the profile's overall score."""

    group: str
    score: float
    weight: float  # renormalized over available groups only
    weighted_score: float
    contribution_pct: float | None  # None when overall == 0


@dataclass(frozen=True)
class ProfileScore:
    """Outcome of scoring one stock under one strategy profile."""

    profile: str
    overall_score: float | None
    confidence: float
    contributions: list[GroupContribution] = field(default_factory=list)
    missing_groups: tuple[str, ...] = ()

    def contributing_groups(self) -> list[str]:
        """Groups that actually contributed, most influential first."""
        scored = [c for c in self.contributions if c.contribution_pct is not None]
        scored.sort(key=lambda c: c.contribution_pct or 0.0, reverse=True)
        return [c.group for c in scored]


def score_profile(
    group_scores: dict[str, float | None],
    profile: str,
    *,
    weights: dict[str, float] | None = None,
) -> ProfileScore:
    """Aggregate per-group scores (0-100) into one overall profile score.

    ``weights`` defaults to the profile's configured weights
    (``configs/strategy_weights.yaml``). Groups that are missing (``None``) or
    carry weight 0 in this profile are excluded and the remaining weights are
    renormalized, so Σ weighted_score == overall and Σ contribution_pct == 1.

    ``confidence`` ∈ [0, 1] reflects evidence coverage: the configured weight
    actually backed by data, scaled by how extreme (decisive) the overall is.
    Missing a 30%-weight group drops confidence far more than missing a 5% one.
    """
    w = weights if weights is not None else weights_for(profile)
    unknown = [g for g in group_scores if g not in GROUPS]
    if unknown:
        raise KeyError(f"unknown score groups: {unknown} (expected from {list(GROUPS)})")

    available = {
        g: v for g, v in group_scores.items() if v is not None and w.get(g, 0.0) > 0.0
    }
    missing = tuple(g for g in GROUPS if g in w and w[g] > 0.0 and group_scores.get(g) is None)

    if not available:
        return ProfileScore(
            profile=profile, overall_score=None, confidence=0.0, missing_groups=missing
        )

    weight_sum = sum(w[g] for g in available)
    overall = sum(available[g] * w[g] for g in available) / weight_sum
    contributions = [
        GroupContribution(
            group=g,
            score=available[g],
            weight=w[g] / weight_sum,
            weighted_score=available[g] * w[g] / weight_sum,
            contribution_pct=(available[g] * w[g] / weight_sum) / overall if overall else None,
        )
        for g in available
    ]
    contributions.sort(key=lambda c: c.contribution_pct or 0.0, reverse=True)

    # Coverage = fraction of the profile's positive weight backed by data.
    positive_weight = sum(v for v in w.values() if v > 0.0)
    coverage = weight_sum / positive_weight if positive_weight else 0.0
    extremity = abs(overall - 55.0) / 45.0
    confidence = round(max(0.0, min(1.0, 0.5 * coverage + 0.5 * coverage * extremity)), 4)

    return ProfileScore(
        profile=profile,
        # Unrounded: Σ weighted_score == overall exactly (persistence rounds).
        overall_score=overall,
        confidence=confidence,
        contributions=contributions,
        missing_groups=missing,
    )
