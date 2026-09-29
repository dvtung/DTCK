"""Unit tests for the EOD freshness probes (src/data/freshness.py).

Regression scope (KI-014): on 2026-09-29 the 15:30 close run failed and nothing
noticed that `prices` still held the 11:30 morning snapshot while `index_prices`
had been frozen since 2026-09-25.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import pytest

from src.data.freshness import (
    EOD_DATASETS,
    ICT,
    expected_session_date,
    is_intraday_snapshot,
    stale_datasets,
)

#: ICT cutoff used by the worker (`SCHEDULER_SESSION_CLOSE_*`).
CLOSE_AT = time(15, 15)


@pytest.mark.parametrize(
    ("ict_clock", "expected"),
    [
        # Tuesday 09:00 — before the close: last completed session is Monday.
        ("2026-09-29 09:00", date(2026, 9, 28)),
        # Tuesday 11:30 — the morning snapshot is not a closed session either.
        ("2026-09-29 11:30", date(2026, 9, 28)),
        # Tuesday 15:30 — the afternoon session just closed.
        ("2026-09-29 15:30", date(2026, 9, 29)),
        # Monday 09:00 — the weekend is skipped, not reported as a session.
        ("2026-09-28 09:00", date(2026, 9, 25)),
        # Saturday/Sunday always resolve to the previous Friday.
        ("2026-10-03 21:00", date(2026, 10, 2)),
        ("2026-10-04 21:00", date(2026, 10, 2)),
    ],
)
def test_expected_session_date_uses_the_last_closed_session(ict_clock: str, expected: date) -> None:
    moment = datetime.strptime(ict_clock, "%Y-%m-%d %H:%M").replace(tzinfo=ICT)
    assert expected_session_date(moment, close_at=CLOSE_AT) == expected
    # Any timezone representation of the same instant must agree.
    assert expected_session_date(moment.astimezone(UTC), close_at=CLOSE_AT) == expected


def test_stale_datasets_reports_missing_and_behind() -> None:
    expected = date(2026, 9, 29)
    assert stale_datasets({"prices": expected, "index_prices": expected}, expected) == []
    assert stale_datasets({"prices": expected, "index_prices": date(2026, 9, 25)}, expected) == [
        "index_prices"
    ]
    assert stale_datasets({"prices": None, "index_prices": None}, expected) == sorted(EOD_DATASETS)
    # Unknown datasets are ignored rather than reported as stale.
    assert stale_datasets({}, expected) == sorted(EOD_DATASETS)


def test_is_intraday_snapshot_detects_the_morning_write_only() -> None:
    trade_date = date(2026, 9, 29)
    # 11:30 ICT write for that same session = morning snapshot.
    morning = datetime(2026, 9, 29, 11, 30, tzinfo=ICT)
    assert is_intraday_snapshot(morning, trade_date=trade_date, close_at=CLOSE_AT) is True
    # 15:35 ICT write = the session close.
    close = datetime(2026, 9, 29, 15, 35, tzinfo=ICT)
    assert is_intraday_snapshot(close, trade_date=trade_date, close_at=CLOSE_AT) is False
    # A write on a later day (late vendor correction) is not an intraday snapshot.
    later = datetime(2026, 9, 30, 9, 0, tzinfo=ICT)
    assert is_intraday_snapshot(later, trade_date=trade_date, close_at=CLOSE_AT) is False
    # No bar at all is "missing", which the caller reports separately.
    assert is_intraday_snapshot(None, trade_date=trade_date, close_at=CLOSE_AT) is False


def test_worker_session_date_wrapper_defaults_to_now() -> None:
    """The worker wrapper (:func:`expected_session_date`) is the production call path."""
    from apps.worker.main import expected_session_date as worker_session_date

    today = worker_session_date()
    assert today.weekday() < 5
    assert (datetime.now(UTC).astimezone(ICT).date() - today) <= timedelta(days=3)
