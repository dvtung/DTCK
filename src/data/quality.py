"""Data quality framework (T005, spec §39 / DATA_ARCHITECTURE §3).

Every dataset batch is scored 0–100 on six dimensions and persisted into
``data_quality_scores``. If ``overall_score`` is below the configured threshold the
row is flagged ``below_threshold`` and the pipeline treats the dataset as **not
usable downstream** (features, signals, backtests) — data is preserved, never
silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import Connection, insert

from src.data.validators import ValidationIssue

# Dimension weights (§39 gives the dimensions, not weights — baseline chosen here
# and deliberately simple; revisit with the backtesting baseline in T009).
WEIGHTS: dict[str, float] = {
    "completeness": 0.25,
    "validity": 0.20,
    "consistency": 0.15,
    "uniqueness": 0.15,
    "freshness": 0.15,
    "accuracy": 0.10,
}

# A dimension that cannot be computed stays None (reported, not faked) and is
# excluded from the weighted mean.
DEFAULT_THRESHOLD = 80.0
FRESHNESS_DECAY_DAYS = 5.0  # linear decay over this many days of lateness


def classify_issue(issue: ValidationIssue) -> str:
    """Map a validation issue to the §39 dimension it penalises."""
    if "duplicate" in issue.message:
        return "uniqueness"
    if issue.message in {"high < low", "close > high", "close < low"}:
        return "consistency"
    return "validity"


@dataclass(frozen=True, slots=True)
class QualityScore:
    """Six §39 dimensions in [0, 1] (``accuracy`` may be ``None``), overall in [0, 100]."""

    dataset: str
    as_of_date: date
    completeness: Decimal | None
    accuracy: Decimal | None
    consistency: Decimal | None
    freshness: Decimal | None
    uniqueness: Decimal | None
    validity: Decimal | None
    overall_score: Decimal
    below_threshold: bool
    rows_total: int
    issues_total: int

    def dimensions(self) -> dict[str, Decimal | None]:
        return {
            "completeness": self.completeness,
            "accuracy": self.accuracy,
            "consistency": self.consistency,
            "freshness": self.freshness,
            "uniqueness": self.uniqueness,
            "validity": self.validity,
        }


def _ratio(numerator: int, denominator: int) -> Decimal | None:
    if denominator <= 0:
        return None
    return Decimal(numerator) / Decimal(denominator)


def freshness_score(latest_date: date | None, as_of_date: date) -> Decimal | None:
    """1.0 when data is current, decaying linearly over ``FRESHNESS_DECAY_DAYS``."""
    if latest_date is None:
        return None
    days_late = (as_of_date - latest_date).days
    if days_late <= 0:
        return Decimal(1)
    raw = Decimal(1) - Decimal(days_late) / Decimal(str(FRESHNESS_DECAY_DAYS))
    return max(Decimal(0), raw)


def overall_from(dims: dict[str, Decimal | None]) -> Decimal:
    """Weighted mean over computable dimensions, renormalised, scaled to 0–100."""
    weight_sum = sum(WEIGHTS[name] for name, value in dims.items() if value is not None)
    if weight_sum <= 0:
        raise ValueError("no quality dimension could be computed for this batch")
    weighted = sum(
        WEIGHTS[name] * float(value) for name, value in dims.items() if value is not None
    )
    return (Decimal(str(weighted / weight_sum)) * Decimal(100)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def compute_quality(
    *,
    dataset: str,
    as_of_date: date,
    rows_total: int,
    issues: list[ValidationIssue],
    expected_keys: int | None = None,
    present_keys: int | None = None,
    latest_date: date | None = None,
    accuracy_ratio: float | None = None,
    threshold: float = DEFAULT_THRESHOLD,
) -> QualityScore:
    """Score one dataset batch.

    ``accuracy_ratio`` is the share of rows matching a trusted benchmark within
    tolerance (§39 "Accuracy"). With no benchmark it stays ``None`` and its weight
    is redistributed over the available dimensions.
    """
    counts = {"uniqueness": 0, "consistency": 0, "validity": 0}
    for issue in issues:
        counts[classify_issue(issue)] += 1

    dims: dict[str, Decimal | None] = {
        "completeness": _ratio(present_keys or 0, expected_keys or 0) if expected_keys else None,
        "accuracy": Decimal(str(accuracy_ratio)) if accuracy_ratio is not None else None,
        "consistency": _ratio(rows_total - counts["consistency"], rows_total),
        "freshness": freshness_score(latest_date, as_of_date),
        "uniqueness": _ratio(rows_total - counts["uniqueness"], rows_total),
        "validity": _ratio(rows_total - counts["validity"], rows_total),
    }
    overall = overall_from(dims)
    return QualityScore(
        dataset=dataset,
        as_of_date=as_of_date,
        completeness=dims["completeness"],
        accuracy=dims["accuracy"],
        consistency=dims["consistency"],
        freshness=dims["freshness"],
        uniqueness=dims["uniqueness"],
        validity=dims["validity"],
        overall_score=overall,
        below_threshold=float(overall) < threshold,
        rows_total=rows_total,
        issues_total=len(issues),
    )


def persist_quality(conn: Connection, score: QualityScore, stock_id: int | None = None) -> None:
    """Append one ``data_quality_scores`` row (insert-only, never updated)."""
    from src.common.models.governance import DataQualityScore

    def pct(value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return (value * Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    conn.execute(
        insert(DataQualityScore.__table__).values(  # type: ignore[arg-type]
            dataset=score.dataset,
            stock_id=stock_id,
            as_of_date=score.as_of_date,
            completeness=pct(score.completeness),
            accuracy=pct(score.accuracy),
            consistency=pct(score.consistency),
            freshness=pct(score.freshness),
            uniqueness=pct(score.uniqueness),
            validity=pct(score.validity),
            overall_score=pct(score.overall_score / Decimal(100)),
            below_threshold=score.below_threshold,
        )
    )


__all__ = [
    "WEIGHTS",
    "DEFAULT_THRESHOLD",
    "QualityScore",
    "classify_issue",
    "freshness_score",
    "overall_from",
    "compute_quality",
    "persist_quality",
]
