"""Integration tests for the freshness probes against the migrated database (KI-014).

Read-only: these probes are what the worker's catch-up and scoring warnings rely
on, so they must be verified against the real schema rather than a mock.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import func, select

from apps.api.db import get_engine
from src.common.models.market import IndexPrice, Price
from src.data.freshness import EOD_DATASETS, latest_ingested_at, latest_trade_dates


def test_latest_trade_dates_match_the_tables(db_ready: None) -> None:
    engine = get_engine()
    latest = latest_trade_dates(engine)
    assert set(latest) == set(EOD_DATASETS)

    with engine.connect() as conn:
        prices_max = conn.execute(select(func.max(Price.trade_date))).scalar()
        index_max = conn.execute(select(func.max(IndexPrice.trade_date))).scalar()

    assert latest["prices"] == prices_max
    assert latest["index_prices"] == index_max
    assert latest["prices"] is None or isinstance(latest["prices"], date)


def test_latest_ingested_at_is_scoped_to_the_requested_session(db_ready: None) -> None:
    engine = get_engine()
    trade_date = latest_trade_dates(engine)["prices"]
    if trade_date is None:
        pytest.skip("prices table is empty — nothing to probe")

    ingested_at = latest_ingested_at(engine, trade_date)
    assert ingested_at is not None
    # A session with no bars must report None instead of leaking another day's write.
    assert latest_ingested_at(engine, date(1990, 1, 1)) is None
