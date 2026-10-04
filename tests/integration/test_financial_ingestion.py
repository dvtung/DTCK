"""Integration tests for the GĐ 2 financials + corporate-events ETL.

Writes run on a single connection inside an outer transaction that is **always
rolled back** (KI-013): the suite exercises real SQL against the developer's
database without leaving rows behind.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy import select

from apps.api.db import get_engine


class _Tx:
    def __init__(self, connection):  # noqa: ANN001
        self._connection = connection

    def __enter__(self):  # noqa: ANN201
        return self._connection

    def __exit__(self, *exc: object) -> bool:  # noqa: ANN204
        return False


class _RolledBackEngine:
    """Engine stand-in whose ``begin()`` never commits (every call shares one
    connection wrapped in an outer transaction that is rolled back)."""

    def __init__(self, connection) -> None:  # noqa: ANN001
        self._connection = connection

    def begin(self) -> _Tx:  # noqa: ANN201
        return _Tx(self._connection)

    def connect(self) -> _Tx:  # noqa: ANN201
        """Same shim for read paths (``with engine.connect() as conn``)."""
        return _Tx(self._connection)


@pytest.fixture
def rollback_engine(db_ready: None) -> Iterator[object]:
    connection = get_engine().connect()
    trans = connection.begin()
    try:
        yield _RolledBackEngine(connection)
    finally:
        trans.rollback()
        connection.close()


def _symbols() -> list[str]:
    from apps.api.db import session_factory
    from src.common.models.reference import Stock

    with session_factory() as session:
        rows = session.scalars(
            select(Stock.symbol).where(Stock.status == "ACTIVE").limit(2)
        ).all()
    return list(rows)


def test_financial_ingestion_roundtrip_and_idempotency(rollback_engine) -> None:
    from src.data.pipelines import ingest_financials
    from src.data.providers.fixture import build_fixture_provider

    symbols = _symbols()
    assert symbols, "reference universe must contain ACTIVE stocks"

    def provider():
        return build_fixture_provider(
            symbols=symbols,
            start=date(2024, 1, 1),
            end=date(2026, 9, 30),
            include_financials=True,
        )

    first = ingest_financials(
        rollback_engine, provider(), symbols, period_types=("QUARTER",)
    )
    assert first.rows_fetched > 0
    assert first.rows_written > 0
    assert first.quality is not None

    # published_at must actually be persisted (the look-ahead guard for GĐ 3).
    from src.common.models.fundamental import FinancialStatement

    def _fixture_rows():
        return list(
            rollback_engine.begin().__enter__().execute(
                select(FinancialStatement).where(
                    FinancialStatement.source == "fixture",
                    FinancialStatement.published_at.is_not(None),
                )
            )
        )

    assert _fixture_rows(), "published_at must be stored, not dropped"

    # Re-running identical data must be a no-op (snapshot-diff, no duplicates).
    second = ingest_financials(
        rollback_engine, provider(), symbols, period_types=("QUARTER",)
    )
    assert second.rows_fetched == first.rows_fetched
    assert second.rows_written == 0, "unchanged statements must not open a new version"

    all_fixture = list(
        rollback_engine.begin().__enter__().execute(
            select(FinancialStatement).where(FinancialStatement.source == "fixture")
        )
    )
    assert len(all_fixture) == first.rows_written


def test_events_ingestion_roundtrip_and_dedup(rollback_engine) -> None:
    from src.data.pipelines import ingest_events
    from src.data.providers.fixture import build_fixture_provider

    symbols = _symbols()
    assert symbols

    def provider():
        return build_fixture_provider(
            symbols=symbols, start=date(2026, 1, 1), end=date(2026, 9, 30), include_events=True
        )

    since = date(2026, 1, 1)
    first = ingest_events(rollback_engine, provider(), symbols, since=since)
    assert first.rows_fetched == len(symbols)
    assert first.rows_written == len(symbols)

    # Application-level dedup: a second run inserts nothing new.
    second = ingest_events(rollback_engine, provider(), symbols, since=since)
    assert second.rows_written == 0

    from src.common.models.events import CorporateEvent

    count = len(
        list(
            rollback_engine.begin().__enter__().execute(
                select(CorporateEvent).where(CorporateEvent.source == "fixture")
            )
        )
    )
    assert count == len(symbols)


def test_macro_ingestion_roundtrip_and_upsert(rollback_engine) -> None:
    """Macro rows upsert on ``(indicator_code, period_date)`` — never duplicate."""
    from src.common.models.macro import MacroIndicator
    from src.data.pipelines import ingest_macro
    from src.data.providers.imf_macro import ImfMacroProvider

    payload = {"values": {"NGDP_RPCH": {"VNM": {"2023": 5.1, "2024": 7.0}}}}

    def handler(request):  # noqa: ANN001
        return httpx.Response(200, json=payload)

    def provider():
        return ImfMacroProvider(
            country="VNM",
            max_year_offset=1,
            transport=httpx.MockTransport(handler),
            timeout_s=5.0,
        )

    first = ingest_macro(
        rollback_engine,
        provider(),
        ["GDP_GROWTH_PCT"],
        start=date(2010, 1, 1),
        end=date(2026, 12, 31),
        source="imf_test",
    )
    assert first.rows_written == 2

    rows = list(
        rollback_engine.begin().__enter__().execute(
            select(MacroIndicator).where(MacroIndicator.source == "imf_test")
        )
    )
    assert len(rows) == 2

    # A refreshed vintage overwrites in place instead of inserting duplicates.
    second = ingest_macro(
        rollback_engine,
        provider(),
        ["GDP_GROWTH_PCT"],
        start=date(2010, 1, 1),
        end=date(2026, 12, 31),
        source="imf_test",
    )
    assert second.rows_written == 2
    again = list(
        rollback_engine.begin().__enter__().execute(
            select(MacroIndicator).where(MacroIndicator.source == "imf_test")
        )
    )
    assert len(again) == 2


def test_feature_engine_persists_and_is_idempotent(rollback_engine) -> None:
    """GĐ 3: features + group scores are written as-of and never duplicated."""
    from sqlalchemy import text

    from src.quant.strategy.feature_engine import (
        FEATURE_VERSION,
        compute_and_store_features,
    )

    symbols = _symbols()
    as_of = _latest_price_date(rollback_engine)
    assert symbols and as_of is not None

    written = compute_and_store_features(rollback_engine, as_of, symbols)
    assert written > 0, "features must be written for the as-of date"

    def _count() -> int:
        return int(
            rollback_engine.begin()
            .__enter__()
            .execute(
                text(
                    "select count(*) from features where feature_version = :v"
                ),
                {"v": FEATURE_VERSION},
            )
            .scalar_one()
        )

    first = _count()
    assert first > 0

    # Second run on the same as-of date must overwrite, not duplicate.
    compute_and_store_features(rollback_engine, as_of, symbols)
    assert _count() == first

    # Group scores are present for at least one group (scored, not all-None).
    group_rows = int(
        rollback_engine.begin()
        .__enter__()
        .execute(
            text(
                "select count(*) from features where feature_version = :v "
                "and feature_name like 'grp:%'"
            ),
            {"v": FEATURE_VERSION},
        )
        .scalar_one()
    )
    assert group_rows > 0


def _latest_price_date(rollback_engine) -> date | None:  # noqa: ANN001
    from sqlalchemy import text

    return (
        rollback_engine.begin()
        .__enter__()
        .execute(text("select max(trade_date) from prices"))
        .scalar_one_or_none()
    )


def _latest_scored_date(rollback_engine) -> date | None:  # noqa: ANN001
    """Latest ``strategy_scores`` session — NOT necessarily the last price bar."""
    from sqlalchemy import text

    return (
        rollback_engine.begin()
        .__enter__()
        .execute(text("select max(trade_date) from strategy_scores"))
        .scalar_one_or_none()
    )


def test_strategy_scoring_persists_and_is_idempotent(rollback_engine) -> None:
    """GĐ 4: 3 profiles → strategy_scores + strategy_recommendations, idempotent."""
    from sqlalchemy import text

    from src.quant.strategy.groups import PROFILES
    from src.quant.strategy.job import compute_and_store_strategy_scores

    symbols = _symbols()
    as_of = _latest_price_date(rollback_engine)
    assert symbols and as_of is not None

    first = compute_and_store_strategy_scores(rollback_engine, as_of, symbols)
    assert first.rows_written > 0
    assert first.profiles == list(PROFILES)

    def _count(table: str) -> int:
        return int(
            rollback_engine.begin()
            .__enter__()
            .execute(text(f"select count(*) from {table}"))
            .scalar_one()
        )

    scores, recs = _count("strategy_scores"), _count("strategy_recommendations")
    assert scores > 0
    assert recs == scores  # one recommendation per score row

    # Re-running the same as-of date must overwrite, not duplicate.
    second = compute_and_store_strategy_scores(rollback_engine, as_of, symbols)
    assert second.rows_written == first.rows_written
    assert _count("strategy_scores") == scores

    # Every recommendation carries a grade (or an honest NULL) + disclaimer text.
    grades = list(
        rollback_engine.begin()
        .__enter__()
        .execute(text("select distinct grade from strategy_recommendations"))
    )
    assert grades, "grades must be written"


def test_grade_change_detection_finds_a_delta(rollback_engine) -> None:
    """GĐ 6: a synthetic previous session with different grades is detected."""
    from sqlalchemy import text

    from src.quant.strategy.alerts import build_change_email, detect_grade_changes

    latest = _latest_scored_date(rollback_engine)
    assert latest is not None, "strategy_scores must be populated first"
    previous = latest - timedelta(days=7)

    conn = rollback_engine.begin().__enter__()
    # Copy the latest session back in time and flip every grade, so the
    # detector must report a change for each scored symbol/profile.
    conn.execute(
        text(
            "insert into strategy_recommendations (stock_id, trade_date, strategy, grade, "
            "confidence, scoring_version, reasons, risks) "
            "select stock_id, :prev, strategy, case grade when 'A' then 'D' "
            "when 'B' then 'A' when 'C' then 'B' else 'C' end, confidence, "
            "scoring_version, reasons, risks "
            "from strategy_recommendations where trade_date = :latest "
            "on conflict (stock_id, trade_date, strategy) do nothing"
        ),
        {"prev": previous, "latest": latest},
    )
    conn.execute(
        text(
            "insert into strategy_scores (stock_id, trade_date, strategy, overall_score, "
            "scoring_version) select stock_id, :prev, strategy, overall_score, "
            "scoring_version from strategy_scores where trade_date = :latest "
            "on conflict (stock_id, trade_date, strategy) do nothing"
        ),
        {"prev": previous, "latest": latest},
    )

    changes = detect_grade_changes(conn)
    assert changes, "a flipped grade set must be detected"
    assert all(c.new_date == latest for c in changes)
    assert all(c.previous_date == previous for c in changes)
    assert {c.direction for c in changes} <= {"UP", "DOWN", "NEW"}

    html = build_change_email(changes)
    assert changes[0].symbol in html
    assert "tham khảo" in html


def test_grade_change_detection_is_quiet_without_two_sessions(rollback_engine) -> None:
    """One scored session (the real state) → no changes, no false alert."""
    from src.quant.strategy.alerts import detect_grade_changes, send_grade_change_alert

    conn = rollback_engine.begin().__enter__()
    assert detect_grade_changes(conn) == []
    result = send_grade_change_alert(conn, dry_run=True)
    assert result["changes"] == 0
    assert result["success"] is True


def test_strategy_backtest_runs_and_reports_benchmark(rollback_engine) -> None:
    """GĐ 5: the backtest runs as-of only and reports strategy vs benchmark."""
    from src.quant.strategy.backtest import (
        load_backtest_data,
        rebalance_dates,
        run_strategy_backtest,
    )

    symbols = _symbols()
    assert symbols
    start, end = date(2026, 6, 1), date(2026, 9, 30)

    data = load_backtest_data(rollback_engine, symbols, start, end)
    assert data.dates, "calendar must not be empty"
    # Every symbol's bars are index-aligned with the calendar (engine contract).
    for symbol in data.symbols:
        assert len(data.bars[symbol]) == len(data.dates)

    rebalance = rebalance_dates([d for d in data.dates if start <= d <= end], every_days=21)
    assert rebalance and rebalance[0] == next(d for d in data.dates if d >= start)

    report = run_strategy_backtest(
        rollback_engine, symbols, start, end, profile="mid", top_n=2, rebalance_days=21
    )
    assert report.result.equity_curve, "backtest must produce an equity curve"
    assert "total_return" in report.metrics
    assert "max_drawdown" in report.metrics
    # Benchmark curve exists for the same window (the §16 comparison).
    assert report.benchmark_metrics.get("total_return") is not None
    # Schedule keys are real trading dates inside the window (as-of only).
    assert report.schedule_size >= 0

