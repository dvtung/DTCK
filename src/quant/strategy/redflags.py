"""Red-flag (exclusion) filter driven by ``configs/redflag_thresholds.yaml``.

Every threshold lives in config; this module only evaluates *provided* inputs
against those thresholds. ``None`` inputs mean "no data" — they never trigger
a flag (absence of evidence is not evidence of guilt) but they are reported
back so the caller can lower the score confidence instead of guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from src.quant.strategy.config import REPO_ROOT

DEFAULT_REDFLAG_PATH = REPO_ROOT / "configs" / "redflag_thresholds.yaml"

__all__ = [
    "DEFAULT_REDFLAG_PATH",
    "RedFlag",
    "RedFlagInputs",
    "RedFlagResult",
    "RedFlagThresholds",
    "evaluate_redflags",
    "load_redflag_thresholds",
]


@dataclass(frozen=True, slots=True)
class RedFlagThresholds:
    """Validated thresholds from ``redflag_thresholds.yaml``."""

    version: str
    min_avg_value_20d_vnd: float
    min_consecutive_loss_years: int
    max_debt_to_equity: float | None
    industry_debt_to_equity: dict[str, float | None]


@dataclass(frozen=True, slots=True)
class RedFlagInputs:
    """Observable facts about one stock (None = unknown, never guessed)."""

    avg_value_20d_vnd: float | None = None
    consecutive_loss_years: int | None = None
    operating_cash_flow_negative: bool | None = None
    debt_to_equity: float | None = None
    industry: str | None = None  # reference-data industry key (e.g. "banking")
    trading_status: str | None = None  # NORMAL | WARNING | CONTROL | RESTRICTED
    audit_opinion: str | None = None  # UNQUALIFIED | QUALIFIED | ADVERSE | DISCLAIMER


@dataclass(frozen=True, slots=True)
class RedFlag:
    """One triggered flag with the threshold that fired."""

    code: str
    detail: str
    threshold: float | str | None = None


@dataclass(frozen=True, slots=True)
class RedFlagResult:
    """Flags raised plus the inputs that could not be checked."""

    flags: tuple[RedFlag, ...] = ()
    unchecked: tuple[str, ...] = ()  # input fields that were None


@lru_cache(maxsize=1)
def load_redflag_thresholds(path: str | None = None) -> RedFlagThresholds:
    """Load and validate ``configs/redflag_thresholds.yaml``."""
    target = Path(path) if path else DEFAULT_REDFLAG_PATH
    with target.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{target}: expected a YAML mapping")

    version = data.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError(f"{target}: missing 'version'")

    liquidity = data.get("liquidity") or {}
    profitability = data.get("profitability") or {}
    leverage = data.get("leverage") or {}
    overrides = leverage.get("industry_overrides") or {}
    if not isinstance(overrides, dict):
        raise ValueError(f"{target}: leverage.industry_overrides must be a mapping")

    max_de = leverage.get("max_debt_to_equity")
    return RedFlagThresholds(
        version=version,
        min_avg_value_20d_vnd=float(liquidity.get("min_avg_value_20d_vnd", 0.0)),
        min_consecutive_loss_years=int(profitability.get("min_consecutive_loss_years", 2)),
        max_debt_to_equity=float(max_de) if max_de is not None else None,
        industry_debt_to_equity={
            str(k): (float(v) if v is not None else None) for k, v in overrides.items()
        },
    )


def evaluate_redflags(
    inputs: RedFlagInputs,
    thresholds: RedFlagThresholds | None = None,
) -> RedFlagResult:
    """Evaluate one stock against the configured thresholds.

    Deterministic and side-effect free. Inputs left ``None`` are collected in
    ``unchecked`` so the scoring step can report reduced coverage instead of
    inventing a value.
    """
    t = thresholds or load_redflag_thresholds()
    flags: list[RedFlag] = []
    unchecked: list[str] = []

    # --- liquidity ---------------------------------------------------------
    if inputs.avg_value_20d_vnd is None:
        unchecked.append("avg_value_20d_vnd")
    elif inputs.avg_value_20d_vnd < t.min_avg_value_20d_vnd:
        flags.append(
            RedFlag(
                code="low_liquidity",
                detail=(
                    f"GTGD bình quân 20 phiên {inputs.avg_value_20d_vnd:,.0f} VND "
                    f"dưới ngưỡng {t.min_avg_value_20d_vnd:,.0f} VND"
                ),
                threshold=t.min_avg_value_20d_vnd,
            )
        )

    # --- sustained losses + negative operating cash flow -------------------
    if inputs.consecutive_loss_years is None:
        unchecked.append("consecutive_loss_years")
    elif (
        inputs.consecutive_loss_years >= t.min_consecutive_loss_years
        and inputs.operating_cash_flow_negative is True
    ):
        flags.append(
            RedFlag(
                code="loss_negative_ocf",
                detail=(
                    f"Lỗ {inputs.consecutive_loss_years} năm liên tiếp "
                    f"(ngưỡng {t.min_consecutive_loss_years}) kèm lưu lượng kinh doanh âm"
                ),
                threshold=t.min_consecutive_loss_years,
            )
        )
    if inputs.operating_cash_flow_negative is None:
        unchecked.append("operating_cash_flow_negative")

    # --- leverage (industry-aware) ----------------------------------------
    de_limit = (
        t.industry_debt_to_equity.get(inputs.industry, t.max_debt_to_equity)
        if inputs.industry
        else t.max_debt_to_equity
    )
    if de_limit is None:
        pass  # industry explicitly exempt from the generic D/E rule
    elif inputs.debt_to_equity is None:
        unchecked.append("debt_to_equity")
    elif inputs.debt_to_equity > de_limit:
        flags.append(
            RedFlag(
                code="high_leverage",
                detail=(
                    f"Nợ/Vốn chủ {inputs.debt_to_equity:.2f} vượt ngưỡng {de_limit:.2f}"
                    + (f" (ngành {inputs.industry})" if inputs.industry else "")
                ),
                threshold=de_limit,
            )
        )

    # --- regulatory / audit statuses (fixed vocabularies) ------------------
    if inputs.trading_status is None:
        unchecked.append("trading_status")
    elif inputs.trading_status != "NORMAL":
        flags.append(
            RedFlag(
                code=f"trading_{inputs.trading_status.lower()}",
                detail=f"Trạng thái giao dịch: {inputs.trading_status}",
                threshold="NORMAL",
            )
        )

    if inputs.audit_opinion is None:
        unchecked.append("audit_opinion")
    elif inputs.audit_opinion != "UNQUALIFIED":
        flags.append(
            RedFlag(
                code=f"audit_{inputs.audit_opinion.lower()}",
                detail=f"Ý kiến kiểm toán: {inputs.audit_opinion}",
                threshold="UNQUALIFIED",
            )
        )

    return RedFlagResult(flags=tuple(flags), unchecked=tuple(unchecked))
