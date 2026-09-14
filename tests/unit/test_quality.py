"""Unit tests for T005 — data quality scoring framework (spec §39).

Tests the six-dimension scoring model: completeness, accuracy, consistency,
freshness, uniqueness, validity — and the threshold gate.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.data.quality import (
    DEFAULT_THRESHOLD,
    _ratio,
    classify_issue,
    compute_quality,
    freshness_score,
    overall_from,
)
from src.data.validators import ValidationIssue

YESTERDAY = date(2026, 9, 13)
TODAY = date(2026, 9, 14)


def issue(dataset: str, msg: str) -> ValidationIssue:
    return ValidationIssue(dataset, "key", "field", msg)


def _f(value: Decimal | None) -> float:
    assert value is not None
    return float(value)


# --------------------------------------------------------------------------- #
#  _ratio
# --------------------------------------------------------------------------- #


class TestRatio:
    def test_zero_denominator_returns_none(self):
        assert _ratio(0, 0) is None

    def test_nonzero_denominator(self):
        result = _ratio(5, 10)
        assert result == Decimal("0.5")


# --------------------------------------------------------------------------- #
#  Freshness
# --------------------------------------------------------------------------- #


class TestFreshness:
    def test_current_data_returns_1(self):
        assert freshness_score(TODAY, TODAY) == Decimal("1")

    def test_future_returns_1(self):
        future = date(2026, 9, 20)
        assert freshness_score(future, TODAY) == Decimal("1")

    def test_none_returns_none(self):
        assert freshness_score(None, TODAY) is None

    def test_one_day_late(self):
        result = freshness_score(YESTERDAY, TODAY)
        assert result == Decimal("0.8")

    def test_five_days_late_returns_0(self):
        old = date(2026, 9, 9)
        result = freshness_score(old, TODAY)
        assert float(result) == pytest.approx(0.0, abs=0.01)

    def test_beyond_decay_returns_0(self):
        ancient = date(2026, 1, 1)
        result = freshness_score(ancient, TODAY)
        assert float(result) == pytest.approx(0.0, abs=0.01)


# --------------------------------------------------------------------------- #
#  overall_from
# --------------------------------------------------------------------------- #


class TestOverallFrom:
    def test_all_dimensions_none_raises(self):
        dims = {"completeness": None, "accuracy": None}
        with pytest.raises(ValueError, match="no quality dimension"):
            overall_from(dims)

    def test_full_score(self):
        dims = {
            "completeness": Decimal("1.0"),
            "validity": Decimal("1.0"),
            "consistency": Decimal("1.0"),
            "uniqueness": Decimal("1.0"),
            "freshness": Decimal("1.0"),
            "accuracy": Decimal("1.0"),
        }
        assert overall_from(dims) == Decimal("100.00")

    def test_partial_dimensions_renormalized(self):
        dims = {
            "completeness": Decimal("0.5"),
            "validity": Decimal("1.0"),
            "accuracy": None,
        }
        result = overall_from(dims)
        assert float(result) == pytest.approx(72.22, abs=0.01)


# --------------------------------------------------------------------------- #
#  classify_issue
# --------------------------------------------------------------------------- #


class TestClassifyIssue:
    def test_duplicate_is_uniqueness(self):
        issue_ = ValidationIssue("prices", "k", "f", "duplicate (symbol, trade_date)")
        assert classify_issue(issue_) == "uniqueness"

    def test_high_low_is_consistency(self):
        issue_ = ValidationIssue("prices", "k", "f", "high < low")
        assert classify_issue(issue_) == "consistency"

    def test_close_high_is_consistency(self):
        issue_ = ValidationIssue("prices", "k", "f", "close > high")
        assert classify_issue(issue_) == "consistency"

    def test_other_is_validity(self):
        issue_ = ValidationIssue("prices", "k", "f", "must be > 0")
        assert classify_issue(issue_) == "validity"


# --------------------------------------------------------------------------- #
#  compute_quality
# --------------------------------------------------------------------------- #


class TestComputeQuality:
    def test_clean_batch_perfect_score(self):
        score = compute_quality(
            dataset="prices",
            as_of_date=TODAY,
            rows_total=5,
            issues=[],
            expected_keys=5,
            present_keys=5,
            latest_date=TODAY,
        )
        assert float(score.overall_score) == pytest.approx(100.0, abs=0.01)
        assert not score.below_threshold

    def test_duplicate_drops_uniqueness(self):
        dup = issue("prices", "duplicate (symbol, trade_date)")
        score = compute_quality(
            dataset="prices",
            as_of_date=TODAY,
            rows_total=5,
            issues=[dup],
            expected_keys=5,
            present_keys=5,
            latest_date=TODAY,
        )
        assert _f(score.uniqueness) == pytest.approx(0.8, abs=0.01)
        assert float(score.overall_score) == pytest.approx(96.67, abs=0.01)

    def test_consistency_issue(self):
        issue_ = issue("prices", "high < low")
        score = compute_quality(
            dataset="prices",
            as_of_date=TODAY,
            rows_total=4,
            issues=[issue_],
            expected_keys=4,
            present_keys=4,
            latest_date=TODAY,
        )
        assert _f(score.consistency) == pytest.approx(0.75, abs=0.01)

    def test_validity_issue(self):
        issue_ = issue("prices", "must be > 0")
        score = compute_quality(
            dataset="prices",
            as_of_date=TODAY,
            rows_total=4,
            issues=[issue_],
            expected_keys=4,
            present_keys=4,
            latest_date=TODAY,
        )
        assert _f(score.validity) == pytest.approx(0.75, abs=0.01)

    def test_low_completeness(self):
        score = compute_quality(
            dataset="prices",
            as_of_date=TODAY,
            rows_total=10,
            issues=[],
            expected_keys=10,
            present_keys=5,
            latest_date=TODAY,
        )
        assert _f(score.completeness) == pytest.approx(0.5, abs=0.01)

    def test_incomplete_keys_no_completeness(self):
        score = compute_quality(
            dataset="prices",
            as_of_date=TODAY,
            rows_total=10,
            issues=[],
            expected_keys=None,
            present_keys=None,
            latest_date=TODAY,
        )
        assert score.completeness is None

    def test_below_threshold_flag(self):
        score = compute_quality(
            dataset="prices",
            as_of_date=TODAY,
            rows_total=10,
            issues=[issue("prices", "must be > 0") for _ in range(10)],
            expected_keys=10,
            present_keys=10,
            latest_date=TODAY,
            threshold=99.0,
        )
        assert score.below_threshold is True

    def test_above_threshold_flag(self):
        score = compute_quality(
            dataset="prices",
            as_of_date=TODAY,
            rows_total=5,
            issues=[],
            expected_keys=5,
            present_keys=5,
            latest_date=TODAY,
            threshold=50.0,
        )
        assert score.below_threshold is False

    def test_accuracy_dimension(self):
        score = compute_quality(
            dataset="prices",
            as_of_date=TODAY,
            rows_total=10,
            issues=[],
            expected_keys=10,
            present_keys=10,
            latest_date=TODAY,
            accuracy_ratio=0.9,
            threshold=DEFAULT_THRESHOLD,
        )
        assert _f(score.accuracy) == pytest.approx(0.9, abs=0.01)
        assert float(score.overall_score) == pytest.approx(99.0, abs=0.01)

    def test_news_score_no_completeness(self):
        score = compute_quality(
            dataset="news",
            as_of_date=TODAY,
            rows_total=5,
            issues=[],
            expected_keys=None,
            present_keys=None,
            latest_date=TODAY,
        )
        assert score.completeness is None
        assert float(score.overall_score) == pytest.approx(100.0, abs=0.01)

    def test_quality_score_dimensions_dict(self):
        score = compute_quality(
            dataset="prices",
            as_of_date=TODAY,
            rows_total=1,
            issues=[],
            expected_keys=1,
            present_keys=1,
            latest_date=TODAY,
        )
        dims = score.dimensions()
        assert set(dims.keys()) == {
            "completeness",
            "accuracy",
            "consistency",
            "freshness",
            "uniqueness",
            "validity",
        }
        assert score.dataset == "prices"
        assert score.as_of_date == TODAY
        assert score.rows_total == 1
        assert score.issues_total == 0
