"""Dataset freshness probes for the EOD scheduler (KI-014).

The decision logic lives in pure functions so the scheduler's behaviour is
unit-testable without a clock or a database; only :func:`latest_trade_dates` and
:func:`latest_ingested_at` touch Postgres.

Why this exists: on 2026-09-29 the 15:30 close run failed (SSI ``502`` on
``Market/AccessToken``, every fallback down). The 11:30 morning snapshot stayed in
``prices`` as if it were the day's close, the 16:00 scoring job silently re-scored
it, and ``index_prices`` had been frozen since 2026-09-25 because the scheduled
job never ingested indices at all.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

if TYPE_CHECKING:  # pragma: no cover — annotations only
    from sqlalchemy import Engine

#: Vietnamese market timezone used by every schedule in this project.
ICT = ZoneInfo("Asia/Ho_Chi_Minh")

#: Datasets the trading-day EOD job must keep current.
EOD_DATASETS: tuple[str, ...] = ("prices", "index_prices")


def now_ict() -> datetime:
    """Current time in market timezone (injectable in tests via ``now`` args)."""
    return datetime.now(UTC).astimezone(ICT)


def expected_session_date(now: datetime, *, close_at: time) -> date:
    """Latest ICT trading date whose session has already closed at ``now``.

    Before the afternoon close cutoff the last *completed* session is the previous
    weekday (Monday 11:00 → Friday), so weekend and in-progress sessions are never
    reported as "expected" data.
    """
    local = now.astimezone(ICT)
    day = local.date()
    if local.timetz().replace(tzinfo=None) < close_at:
        day -= timedelta(days=1)
    while day.weekday() >= 5:  # Sat/Sun → previous Friday
        day -= timedelta(days=1)
    return day


def stale_datasets(latest: Mapping[str, date | None], expected: date) -> list[str]:
    """Scheduled datasets whose newest row is older than ``expected`` (or absent)."""
    stale: list[str] = []
    for name in EOD_DATASETS:
        newest = latest.get(name)
        if newest is None or newest < expected:
            stale.append(name)
    return sorted(stale)


def is_intraday_snapshot(
    ingested_at: datetime | None,
    *,
    trade_date: date,
    close_at: time,
) -> bool:
    """True when a bar for ``trade_date`` was written before that session closed.

    The 11:30 run legitimately stores the morning snapshot; anything scored from a
    bar whose newest write predates the close cutoff is provisional, not the close.
    """
    if ingested_at is None:
        return False
    local = ingested_at.astimezone(ICT)
    if local.date() != trade_date:
        return False
    return local.timetz().replace(tzinfo=None) < close_at


def latest_trade_dates(engine: Engine) -> dict[str, date | None]:
    """Newest ``trade_date`` per EOD dataset (``None`` when the table is empty)."""
    from src.common.models.market import IndexPrice, Price

    dates: dict[str, date | None] = {}
    with engine.connect() as conn:
        prices_max = conn.execute(select(func.max(Price.trade_date))).scalar()
        index_max = conn.execute(select(func.max(IndexPrice.trade_date))).scalar()
    dates["prices"] = prices_max if isinstance(prices_max, date) else None
    dates["index_prices"] = index_max if isinstance(index_max, date) else None
    return dates


def latest_ingested_at(engine: Engine, trade_date: date) -> datetime | None:
    """Newest ``ingested_at`` among the stock bars stored for ``trade_date``."""
    from src.common.models.market import Price

    with engine.connect() as conn:
        value = conn.execute(
            select(func.max(Price.ingested_at)).where(Price.trade_date == trade_date)
        ).scalar()
    return value if isinstance(value, datetime) else None


__all__ = [
    "EOD_DATASETS",
    "ICT",
    "expected_session_date",
    "is_intraday_snapshot",
    "latest_ingested_at",
    "latest_trade_dates",
    "now_ict",
    "stale_datasets",
]
