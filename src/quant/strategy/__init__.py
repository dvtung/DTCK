"""Multi-strategy stock scoring module (Chấm điểm & Gợi ý cổ phiếu đa chiến lược).

Pipeline (spec): features → red flags → 7-group scoring → grade/explanation.
Persists into ``strategy_scores`` / ``strategy_recommendations``; reads its
weights from ``configs/strategy_weights.yaml`` and thresholds from
``configs/redflag_thresholds.yaml`` — nothing is hard-coded.

Stage GĐ 1 delivers config loading, group scoring, red-flag evaluation and
grade/explanation (pure, tested). The feature engine (GĐ 3), the daily job +
persistence (GĐ 4), backtesting (GĐ 5) and API/dashboard (GĐ 6) build on top.
"""

from __future__ import annotations

from src.quant.strategy.config import (
    StrategyConfig,
    StrategyConfigError,
    load_strategy_config,
    weights_for,
)
from src.quant.strategy.groups import GROUP_COLUMNS, GROUPS, PROFILES
from src.quant.strategy.recommend import DISCLAIMER, Recommendation, build_recommendation
from src.quant.strategy.redflags import (
    RedFlag,
    RedFlagInputs,
    RedFlagResult,
    RedFlagThresholds,
    evaluate_redflags,
    load_redflag_thresholds,
)
from src.quant.strategy.scoring import GroupContribution, ProfileScore, score_profile

__all__ = [
    "DISCLAIMER",
    "GROUPS",
    "GROUP_COLUMNS",
    "GroupContribution",
    "PROFILES",
    "ProfileScore",
    "Recommendation",
    "RedFlag",
    "RedFlagInputs",
    "RedFlagResult",
    "RedFlagThresholds",
    "StrategyConfig",
    "StrategyConfigError",
    "build_recommendation",
    "evaluate_redflags",
    "load_redflag_thresholds",
    "load_strategy_config",
    "score_profile",
    "weights_for",
]
