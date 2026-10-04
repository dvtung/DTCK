"""Grade assignment (A/B/C/D) + explanation payload for one profile score.

Deterministic rules from ``configs/strategy_weights.yaml``:

* grade thresholds (A/B/C/D) come from the ``grades`` block;
* profiles in ``require_trend_confirmation`` (e.g. ``short``) may not be
  graded A/B unless an uptrend is confirmed by the caller — a short-term
  score without trend confirmation caps at C.

The explanation lists the strongest contributing groups as reasons and the
missing/highest-risk groups as risks. Every payload carries the §3
disclaimer: reference only, never personalised investment advice.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from src.quant.strategy.config import load_strategy_config
from src.quant.strategy.scoring import ProfileScore

__all__ = [
    "DISCLAIMER",
    "PriceLevels",
    "Recommendation",
    "atr",
    "build_recommendation",
    "price_levels",
    "trend_confirmed",
]


@dataclass(frozen=True)
class PriceLevels:
    """Deterministic reference levels; every field is ``None`` when unknown."""

    buy_zone_low: float | None = None
    buy_zone_high: float | None = None
    stop_loss: float | None = None
    target_price: float | None = None
    rr_ratio: float | None = None

#: §3 non-goals — always returned with a recommendation.
DISCLAIMER = (
    "Kết quả chỉ mang tính tham khảo, không phải khuyến nghị đầu tư cá nhân. "
    "Hệ thống không cam kết lợi nhuận và không thay thế chuyên gia tư vấn."
)




@dataclass(frozen=True)
class Recommendation:
    """Grade + explanation for one stock under one profile."""

    profile: str
    grade: str | None  # None when the overall score is None (no fabricated grade)
    overall_score: float | None
    confidence: float
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    disclaimer: str = DISCLAIMER

    def as_dict(self) -> dict[str, object]:
        """JSON-ready payload (API/dashboard/email consumers)."""
        return {
            "profile": self.profile,
            "grade": self.grade,
            "overall_score": self.overall_score,
            "confidence": self.confidence,
            "reasons": list(self.reasons),
            "risks": list(self.risks),
            "disclaimer": self.disclaimer,
        }


def _assign_grade(overall: float, cfg_grades: dict[str, float], capped: bool) -> str:
    """Letter grade from thresholds; ``capped`` prevents A/B (trend unconfirmed)."""
    if overall >= cfg_grades["A"] and not capped:
        return "A"
    if overall >= cfg_grades["B"] and not capped:
        return "B"
    if overall >= cfg_grades["C"]:
        return "C"
    return "D"


def atr(closes: Sequence[float], period: int = 20) -> float | None:
    """Average true range over ``period`` bars (close-to-close proxy).

    No intraday high/low is stored yet, so the true range is approximated by
    ``|close_t − close_{t−1}|`` — a documented approximation, not the vendor's
    ATR. Returns ``None`` when there are fewer than ``period + 1`` bars.
    """
    if len(closes) < period + 1:
        return None
    window = list(closes)[-(period + 1) :]
    ranges = [abs(window[i] - window[i - 1]) for i in range(1, len(window))]
    return sum(ranges) / len(ranges)


def price_levels(closes: Sequence[float], *, atr_multiple_stop: float = 2.0) -> PriceLevels:
    """Deterministic buy zone / stop / target from the close and ATR (§16-ish).

    All multiples live here (not in config) because they are *arithmetic*, not
    tunable thresholds; the risk profile itself is a GĐ 5 backtest concern.
    Returns all-``None`` when there is not enough price history.
    """
    if not closes:
        return PriceLevels()
    entry = float(closes[-1])
    band = atr(closes)
    if band is None or band <= 0:
        return PriceLevels()
    low = entry - band
    high = entry + 0.25 * band
    stop = entry - atr_multiple_stop * band
    target = entry + 3.0 * band
    risk = entry - stop
    rr = (target - entry) / risk if risk > 0 else None
    return PriceLevels(
        buy_zone_low=round(low, 2),
        buy_zone_high=round(high, 2),
        stop_loss=round(stop, 2),
        target_price=round(target, 2),
        rr_ratio=round(rr, 2) if rr is not None else None,
    )


def trend_confirmed(closes: Sequence[float]) -> bool:
    """``close > SMA20 > SMA50`` — the short-term profile's confirmation rule.

    Deterministic and computable from stored closes only; ``False`` when the
    history is too short (never upgrade a grade on missing evidence).
    """
    if len(closes) < 50:
        return False
    sma20 = sum(list(closes)[-20:]) / 20
    sma50 = sum(list(closes)[-50:]) / 50
    return float(closes[-1]) > sma20 > sma50


def build_recommendation(
    score: ProfileScore,
    *,
    trend_confirmed: bool | None = None,
) -> Recommendation:
    """Turn a :class:`ProfileScore` into a grade + explanation.

    ``trend_confirmed`` is only consulted for profiles listed in
    ``require_trend_confirmation`` (currently ``short``). ``None`` means the
    trend could not be determined — treated as *not* confirmed (honest: we do
    not upgrade a grade on missing evidence).
    """
    cfg = load_strategy_config()

    if score.overall_score is None:
        return Recommendation(
            profile=score.profile,
            grade=None,
            overall_score=None,
            confidence=score.confidence,
            risks=["Thiếu dữ liệu để chấm điểm — không xếp hạng."],
        )

    needs_trend = score.profile in cfg.require_trend_confirmation
    trend_ok = trend_confirmed is True
    capped = needs_trend and not trend_ok

    grade = _assign_grade(score.overall_score, cfg.grades, capped)

    reasons: list[str] = []
    top = [c for c in score.contributions if c.contribution_pct is not None]
    top.sort(key=lambda c: c.contribution_pct or 0.0, reverse=True)
    for contrib in top[:3]:
        pct = contrib.contribution_pct or 0.0
        reasons.append(
            f"Nhóm '{contrib.group}' đóng góp {pct:.0%} điểm "
            f"(giá trị {contrib.score:.0f}/100)"
        )
    risks: list[str] = []
    if score.missing_groups:
        risks.append(f"Thiếu dữ liệu nhóm: {', '.join(score.missing_groups)} (điểm tin cậy giảm).")
    if capped:
        risks.append(
            "Chiến lược ngắn hạn chưa xác nhận xu hướng tăng — giới hạn xếp hạng tối đa C."
        )

    return Recommendation(
        profile=score.profile,
        grade=grade,
        overall_score=score.overall_score,
        confidence=score.confidence,
        reasons=reasons,
        risks=risks,
    )
