"""Load + validate ``configs/strategy_weights.yaml`` (weights live in config).

Mirrors ``src/data/providers/registry.py``: YAML is the source of truth, the
code validates it loudly at load time (a profile that does not sum to 1.0 must
never silently produce skewed scores).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from src.quant.strategy.groups import GROUPS, PROFILES

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_STRATEGY_WEIGHTS_PATH = REPO_ROOT / "configs" / "strategy_weights.yaml"

#: Tolerance for float weight sums (YAML decimals like 0.10 are inexact).
WEIGHT_SUM_TOLERANCE = 1e-9


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    """Validated strategy-weights configuration."""

    version: str
    profiles: dict[str, dict[str, float]]
    grades: dict[str, float]
    require_trend_confirmation: tuple[str, ...]


class StrategyConfigError(ValueError):
    """Raised when ``strategy_weights.yaml`` is structurally invalid."""


def _validate(data: dict[str, Any], path: Path) -> StrategyConfig:
    version = data.get("version")
    if not isinstance(version, str) or not version:
        raise StrategyConfigError(f"{path}: missing 'version'")

    raw_profiles = data.get("profiles")
    if not isinstance(raw_profiles, dict):
        raise StrategyConfigError(f"{path}: missing 'profiles'")
    if set(raw_profiles) != set(PROFILES):
        raise StrategyConfigError(
            f"{path}: profiles {sorted(raw_profiles)} != expected {sorted(PROFILES)}"
        )

    profiles: dict[str, dict[str, float]] = {}
    for name in PROFILES:
        raw = raw_profiles[name]
        if not isinstance(raw, dict) or set(raw) != set(GROUPS):
            raise StrategyConfigError(
                f"{path}: profile '{name}' must define exactly the groups {list(GROUPS)}"
            )
        weights = {str(k): float(v) for k, v in raw.items()}
        total = sum(weights.values())
        if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
            raise StrategyConfigError(
                f"{path}: profile '{name}' weights sum to {total!r}, expected 1.0"
            )
        if any(w < 0.0 for w in weights.values()):
            raise StrategyConfigError(f"{path}: profile '{name}' has a negative weight")
        profiles[name] = weights

    raw_grades = data.get("grades")
    if not isinstance(raw_grades, dict) or not raw_grades:
        raise StrategyConfigError(f"{path}: missing 'grades'")
    grades = {str(k): float(v) for k, v in raw_grades.items()}
    # Grades must descend: A threshold > B threshold > C threshold.
    ordered = [grades[k] for k in ("A", "B", "C") if k in grades]
    if len(ordered) != 3 or not all(
        a > b for a, b in zip(ordered, ordered[1:], strict=False)
    ):
        raise StrategyConfigError(f"{path}: grades must define descending A > B > C")

    raw_required = data.get("require_trend_confirmation", [])
    if not isinstance(raw_required, list) or any(p not in PROFILES for p in raw_required):
        raise StrategyConfigError(
            f"{path}: 'require_trend_confirmation' must be a list of {list(PROFILES)}"
        )

    return StrategyConfig(
        version=version,
        profiles=profiles,
        grades=grades,
        require_trend_confirmation=tuple(str(p) for p in raw_required),
    )


@lru_cache(maxsize=1)
def load_strategy_config(path: str | None = None) -> StrategyConfig:
    """Load and validate the strategy weights config (cached per path)."""
    target = Path(path) if path else DEFAULT_STRATEGY_WEIGHTS_PATH
    with target.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise StrategyConfigError(f"{target}: expected a YAML mapping")
    return _validate(data, target)


def weights_for(profile: str, config: StrategyConfig | None = None) -> dict[str, float]:
    """Weights of one profile (raises ``KeyError`` for unknown profiles)."""
    cfg = config or load_strategy_config()
    if profile not in cfg.profiles:
        raise KeyError(f"unknown strategy profile: {profile!r} (expected one of {PROFILES})")
    return cfg.profiles[profile]
