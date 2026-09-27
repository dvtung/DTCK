"""Validators (T004) — reject bad rows before they reach the database.

Checks implement the data-quality framework checks in
``docs/DATA_ARCHITECTURE.md`` §3 (completeness/consistency/uniqueness/validity
feed the T005 scorer in ``src/data/quality.py``; see spec §39).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from src.data.records import EODBar, IndexBar, NewsItem


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One rule violation, traceable to a row key and field."""

    dataset: str
    key: str
    field: str
    message: str

    def __str__(self) -> str:
        return f"{self.dataset}[{self.key}].{self.field}: {self.message}"


def _key_eod(bar: EODBar) -> str:
    return eod_key(bar.symbol, bar.trade_date)


def _key_index(bar: IndexBar) -> str:
    return index_key(bar.index_code, bar.trade_date)


def index_key(index_code: str, trade_date: date) -> str:
    """Canonical row key for an index bar (``CODE@YYYY-MM-DD``)."""
    return f"{index_code}@{trade_date}"


def eod_key(symbol: str, trade_date: date) -> str:
    """Canonical row key for an EOD bar (``SYMBOL@YYYY-MM-DD``)."""
    return f"{symbol}@{trade_date}"


#: Fields whose value must satisfy the OHLC/volume invariants (§39).
OHLC_INVARIANT_FIELDS = frozenset(
    {"open", "high", "low", "close", "volume", "trading_value"}
)


def corrupt_keys(issues: list[ValidationIssue]) -> set[str]:
    """Row keys whose OHLC/volume invariants are violated.

    These bars are corrupt (e.g. Yahoo reported ``high < low``): they stay in
    the issue list so the quality score still penalises the batch, but the
    pipeline drops them from the upsert — bad rows must never reach ``prices``
    (found live in the 2-year backfill: 4 rows on TPB, 2026-09-27).
    """
    return {issue.key for issue in issues if issue.field in OHLC_INVARIANT_FIELDS}


def _key_news(item: NewsItem) -> str:
    return f"{item.source}:{item.title[:60]}"


# --- per-row field/domain checks (validity + consistency) -------------------------------


def _check_ohlc_row(
    dataset: str,
    key: str,
    *,
    open_: Decimal,
    high: Decimal,
    low: Decimal,
    close: Decimal,
    volume: int,
    trading_value: Decimal | None = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    positive = {"open": open_, "high": high, "low": low, "close": close}
    for name, value in positive.items():
        if value <= 0:
            issues.append(ValidationIssue(dataset, key, name, f"must be > 0 (got {value})"))
    if high < low:
        issues.append(ValidationIssue(dataset, key, "high", "high < low"))
    if close > high:
        issues.append(ValidationIssue(dataset, key, "close", "close > high"))
    if close < low:
        issues.append(ValidationIssue(dataset, key, "close", "close < low"))
    if volume < 0:
        issues.append(ValidationIssue(dataset, key, "volume", f"must be >= 0 (got {volume})"))
    if trading_value is not None and trading_value < 0:
        issues.append(
            ValidationIssue(dataset, key, "trading_value", f"must be >= 0 (got {trading_value})")
        )
    return issues


def validate_eod(bars: list[EODBar], *, start: date, end: date) -> list[ValidationIssue]:
    """Field-domain, coherence, window and uniqueness checks for EOD bars."""
    issues: list[ValidationIssue] = []
    seen: set[tuple[str, date]] = set()
    for bar in bars:
        key = _key_eod(bar)
        if (bar.symbol, bar.trade_date) in seen:
            issues.append(
                ValidationIssue("prices", key, "trade_date", "duplicate (symbol, trade_date)")
            )
        seen.add((bar.symbol, bar.trade_date))
        if not start <= bar.trade_date <= end:
            issues.append(ValidationIssue("prices", key, "trade_date", "outside requested window"))
        issues.extend(
            _check_ohlc_row(
                "prices",
                key,
                open_=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                trading_value=bar.trading_value,
            )
        )
    return issues


def validate_index(bars: list[IndexBar], *, start: date, end: date) -> list[ValidationIssue]:
    """Same checks as EOD bars, for index rows."""
    issues: list[ValidationIssue] = []
    seen: set[tuple[str, date]] = set()
    for bar in bars:
        key = _key_index(bar)
        if (bar.index_code, bar.trade_date) in seen:
            issues.append(
                ValidationIssue(
                    "index_prices", key, "trade_date", "duplicate (index_code, trade_date)"
                )
            )
        seen.add((bar.index_code, bar.trade_date))
        if not start <= bar.trade_date <= end:
            issues.append(
                ValidationIssue("index_prices", key, "trade_date", "outside requested window")
            )
        issues.extend(
            _check_ohlc_row(
                "index_prices",
                key,
                open_=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                trading_value=bar.trading_value,
            )
        )
    return issues


def validate_news(items: list[NewsItem], *, now: datetime | None = None) -> list[ValidationIssue]:
    """Non-empty text, bounds on sentiment/importance, no future publication."""
    issues: list[ValidationIssue] = []
    seen: set[tuple[str, str]] = set()
    reference = now or datetime.now().astimezone()

    def _aware(value: datetime) -> datetime:
        """Coerce naive timestamps to local-aware so comparison cannot raise."""
        return value if value.tzinfo else value.astimezone()

    for item in items:
        key = _key_news(item)
        if (item.source, item.title) in seen:
            issues.append(ValidationIssue("news", key, "title", "duplicate (source, title)"))
        seen.add((item.source, item.title))
        if not item.title.strip():
            issues.append(ValidationIssue("news", key, "title", "empty"))
        if not item.content.strip():
            issues.append(ValidationIssue("news", key, "content", "empty"))
        if _aware(item.published_at) > reference:
            issues.append(ValidationIssue("news", key, "published_at", "published in the future"))
        for name, value, low, high in (
            ("sentiment", item.sentiment, Decimal("-1"), Decimal("1")),
            ("importance", item.importance, Decimal("0"), Decimal("1")),
        ):
            if value is not None and not low <= value <= high:
                issues.append(
                    ValidationIssue("news", key, name, f"outside [{low}, {high}] (got {value})")
                )
    return issues


__all__ = [
    "OHLC_INVARIANT_FIELDS",
    "ValidationIssue",
    "corrupt_keys",
    "eod_key",
    "index_key",
    "validate_eod",
    "validate_index",
    "validate_news",
]
