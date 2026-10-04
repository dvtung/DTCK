"""Shared keys for the multi-strategy scoring module.

The seven score groups and three strategy profiles are the vocabulary shared
by ``configs/strategy_weights.yaml``, the feature engine (GĐ 3) and the
scoring/recommendation steps (GĐ 4). Nothing here computes anything — it only
names things so config, code and tests cannot drift apart.
"""

from __future__ import annotations

__all__ = ["GROUPS", "GROUP_COLUMNS", "PROFILES", "GROUP_TECHNICAL"]

#: The seven score groups (0-100 each), in config-file order.
GROUPS: tuple[str, ...] = (
    "technical",
    "moneyflow",
    "growth",
    "quality",
    "valuation",
    "macro",
    "governance",
)

#: Score group -> ``strategy_scores`` column (single source for persistence).
GROUP_COLUMNS: dict[str, str] = {g: f"{g}_score" for g in GROUPS}

#: The three strategy profiles (configs/strategy_weights.yaml ``profiles``).
PROFILES: tuple[str, ...] = ("short", "mid", "long")

GROUP_TECHNICAL = "technical"
