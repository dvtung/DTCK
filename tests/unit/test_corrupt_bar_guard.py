"""Unit tests for the corrupt-bar guard in the ingest pipelines (T015b step 5).

A bar that violates the OHLC/volume invariants must never reach ``prices``
while still being reported as a validation issue (so the §39 quality score
penalises the batch).  Found live: Yahoo returned ``high < low`` on TPB.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.data.records import EODBar
from src.data.validators import corrupt_keys, eod_key, index_key, validate_eod

D = date(2025, 6, 4)


def _bar(symbol: str, **overrides: object) -> EODBar:
    kwargs: dict = {
        "symbol": symbol,
        "exchange": "HOSE",
        "trade_date": D,
        "open": Decimal("10.0"),
        "high": Decimal("11.0"),
        "low": Decimal("9.0"),
        "close": Decimal("10.5"),
        "volume": 1000,
        "trading_value": Decimal("10500.0"),
    }
    kwargs.update(overrides)
    return EODBar(**kwargs)


def test_clean_bar_produces_no_issues() -> None:
    assert validate_eod([_bar("FPT")], start=D, end=D) == []


def test_corrupt_bar_keys_are_identified() -> None:
    bars = [_bar("FPT"), _bar("TPB", high=8.0)]  # high < low
    issues = validate_eod(bars, start=D, end=D)
    assert corrupt_keys(issues) == {eod_key("TPB", D)}


def test_every_invariant_is_covered() -> None:
    """close/low/open/volume violations all yield a corrupt key."""
    cases = [
        _bar("A", high=Decimal("8.0")),
        _bar("B", close=Decimal("12.0")),
        _bar("C", close=Decimal("8.0")),
        _bar("D", volume=-1),
        _bar("E", open=Decimal("0.0")),
    ]
    issues = validate_eod(cases, start=D, end=D)
    assert corrupt_keys(issues) == {eod_key(b.symbol, D) for b in cases}


def test_window_and_duplicate_issues_are_not_corruption() -> None:
    """Informational issues must not trigger a data drop."""
    bars = [_bar("FPT"), _bar("FPT")]
    issues = validate_eod(bars, start=D, end=date(2025, 6, 5))
    assert any(i.field == "trade_date" for i in issues)
    assert corrupt_keys(issues) == set()


def test_key_helpers_are_stable() -> None:
    assert eod_key("FPT", D) == "FPT@2025-06-04"
    assert index_key("VNINDEX", D) == "VNINDEX@2025-06-04"
