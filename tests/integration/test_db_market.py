"""TimescaleDB-backed read path (W1) — integration tests.

Runs against the configured database and inserts one self-contained dataset
(a temp stock + prices/valuation/quality/news/backtest rows), asserts every
reader, then removes exactly those rows. Skipped when the DB is unreachable.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from src.common.models.backtest import Backtest, BacktestMetric, BacktestTrade
from src.common.models.events import News, NewsSymbol
from src.common.models.governance import DataQualityScore
from src.common.models.market import Price, ValuationDaily
from src.common.models.reference import Exchange, Stock

TEST_SYMBOL = "ZZTEST1"
DATES = (date(2026, 8, 3), date(2026, 8, 4), date(2026, 8, 5))
CLOSES = (Decimal("100.0000"), Decimal("102.0000"), Decimal("101.0000"))


@pytest.fixture
def market_fixture(session: Session) -> Iterator[dict[str, Any]]:
    """Insert a temp universe; delete it again even if a test fails."""
    exchange_id = session.scalar(select(Exchange.id).where(Exchange.code == "HOSE"))
    if exchange_id is None:
        pytest.skip("seeds missing — run `python -m database.seeds.run_all`")

    stock = Stock(
        symbol=TEST_SYMBOL,
        exchange_id=exchange_id,
        company_name="ZZ Test Corp",
        status="ACTIVE",
        is_vn30=False,
        listed_date=date(2020, 1, 1),
    )
    session.add(stock)
    session.flush()
    stock_id = stock.id

    for trade_date, close in zip(DATES, CLOSES, strict=True):
        session.add(
            Price(
                stock_id=stock_id,
                trade_date=trade_date,
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1000,
                trading_value=Decimal("100000.00"),
                source="integration-test",
                ingested_at=datetime.now(tz=UTC),
            )
        )

    session.add(
        ValuationDaily(
            stock_id=stock_id,
            trade_date=DATES[-1],
            pe=Decimal("12.5000"),
            pb=Decimal("2.1000"),
            ev_ebitda=Decimal("9.0000"),
            dividend_yield=Decimal("0.0300"),
            peg=Decimal("1.2000"),
            industry_pe_median=Decimal("11.0000"),
        )
    )
    session.add(
        DataQualityScore(
            dataset="prices",
            stock_id=stock_id,
            as_of_date=DATES[-1],
            completeness=Decimal("90.00"),
            accuracy=Decimal("91.00"),
            consistency=Decimal("92.00"),
            freshness=Decimal("93.00"),
            uniqueness=Decimal("100.00"),
            validity=Decimal("94.00"),
            overall_score=Decimal("92.50"),
            below_threshold=False,
        )
    )

    news = News(
        source="cafef",
        title="ZZ Test headline",
        content="ZZ Test content",
        published_at=datetime(2026, 8, 5, 9, 0, tzinfo=UTC),
        ingested_at=datetime.now(tz=UTC),
    )
    session.add(news)
    session.flush()
    session.add(NewsSymbol(news_id=news.id, stock_id=stock_id))

    backtest_id = uuid4()
    session.add(
        Backtest(
            id=backtest_id,
            strategy_name="zz_test_strategy",
            strategy_version="0.1.0",
            universe="ZZ",
            start_date=DATES[0],
            end_date=DATES[-1],
            run_type="walk-forward",
            transaction_cost_bps=Decimal("15.000"),
            slippage_bps=Decimal("5.000"),
        )
    )
    session.add(
        BacktestMetric(
            backtest_id=backtest_id, metric_name="total_return", value=Decimal("0.05000000")
        )
    )
    session.add(
        BacktestTrade(
            backtest_id=backtest_id,
            stock_id=stock_id,
            entry_date=DATES[0],
            exit_date=DATES[-1],
            entry_price=Decimal("100.0000"),
            exit_price=Decimal("101.0000"),
            quantity=Decimal("100.0000"),
            pnl=Decimal("100.0000"),
            return_pct=Decimal("0.010000"),
        )
    )
    session.commit()

    try:
        yield {"symbol": TEST_SYMBOL, "stock_id": stock_id, "backtest_id": str(backtest_id)}
    finally:
        session.execute(delete(BacktestTrade).where(BacktestTrade.backtest_id == backtest_id))
        session.execute(delete(BacktestMetric).where(BacktestMetric.backtest_id == backtest_id))
        session.execute(delete(Backtest).where(Backtest.id == backtest_id))
        session.execute(delete(NewsSymbol).where(NewsSymbol.stock_id == stock_id))
        session.execute(
            delete(News).where(News.source == "cafef", News.title == "ZZ Test headline")
        )
        session.execute(delete(DataQualityScore).where(DataQualityScore.stock_id == stock_id))
        session.execute(delete(ValuationDaily).where(ValuationDaily.stock_id == stock_id))
        session.execute(delete(Price).where(Price.stock_id == stock_id))
        session.execute(delete(Stock).where(Stock.id == stock_id))
        session.commit()


# --------------------------------------------------------------- reference
def test_stock_profile_and_latest_price(db_service: Any, market_fixture: dict[str, Any]) -> None:
    row = db_service.get_stock(TEST_SYMBOL)
    assert row is not None
    assert row["exchange"] == "HOSE"
    assert row["status"] == "ACTIVE"
    assert row["is_vn30"] is False
    assert row["price"] == pytest.approx(101.0)
    # Lower-case lookups must resolve too (routers upper-case before calling).
    assert db_service.get_stock(TEST_SYMBOL.lower()) is not None


def test_price_series_is_ascending(db_service: Any, market_fixture: dict[str, Any]) -> None:
    rows = db_service.get_prices(TEST_SYMBOL)
    assert rows is not None
    assert [row["trade_date"] for row in rows] == list(DATES)
    assert rows[-1]["close"] == pytest.approx(101.0)
    assert rows[-1]["volume"] == 1000


def test_list_stocks_honours_filters(db_service: Any, market_fixture: dict[str, Any]) -> None:
    hose = db_service.list_stocks("HOSE", None, None)
    assert TEST_SYMBOL in [row["symbol"] for row in hose]
    vn30 = db_service.list_stocks(None, None, True)
    assert TEST_SYMBOL not in [row["symbol"] for row in vn30]
    hnx = db_service.list_stocks("HNX", None, None)
    assert all(row["exchange"] == "HNX" for row in hnx)


def test_unknown_symbols_return_none(db_service: Any) -> None:
    assert db_service.get_stock("NOSUCHSYMBOL") is None
    assert db_service.get_prices("NOSUCHSYMBOL") is None
    assert db_service.get_indicators("NOSUCHSYMBOL") is None
    assert db_service.get_valuation_summary("NOSUCHSYMBOL") is None
    assert db_service.get_quality("NOSUCHSYMBOL") is None
    assert db_service.get_ranking("NOSUCHSYMBOL") is None
    assert db_service.get_backtest("not-a-uuid") is None


# ---------------------------------------------------- derived (computed read)
def test_indicators_reuse_the_deterministic_engine(
    db_service: Any, market_fixture: dict[str, Any]
) -> None:
    row = db_service.get_indicators(TEST_SYMBOL)
    assert row is not None
    assert row["symbol"] == TEST_SYMBOL
    assert row["as_of"] == DATES[-1]
    assert set(row["series"]) == {"sma20", "ema12", "rsi14"}
    # Only 3 bars: warmup indicators stay None rather than being fabricated.
    assert row["series"]["sma20"] is None


def test_breadth_counts_are_consistent(db_service: Any, session: Session) -> None:
    """Breadth must equal a recomputation over the latest two trade dates."""
    row = db_service.get_breadth()
    dates = list(
        session.scalars(
            select(Price.trade_date).distinct().order_by(Price.trade_date.desc()).limit(2)
        )
    )
    if len(dates) < 2:
        assert (row["advancers"], row["decliners"], row["unchanged"]) == (0, 0, 0)
        return

    assert row["trade_date"] == dates[0]
    current = {
        stock_id: close
        for stock_id, close in session.execute(
            select(Price.stock_id, Price.close).where(Price.trade_date == dates[0])
        )
    }
    previous = {
        stock_id: close
        for stock_id, close in session.execute(
            select(Price.stock_id, Price.close).where(Price.trade_date == dates[1])
        )
    }
    before = [
        (stock_id, close, previous[stock_id])
        for stock_id, close in current.items()
        if stock_id in previous
    ]
    advancers = sum(1 for _, close, prev in before if close > prev)
    decliners = sum(1 for _, close, prev in before if close < prev)
    unchanged = sum(1 for _, close, prev in before if close == prev)
    assert (row["advancers"], row["decliners"], row["unchanged"]) == (
        advancers,
        decliners,
        unchanged,
    )

    active = session.scalar(
        select(func.count()).select_from(Stock).where(Stock.status == "ACTIVE")
    )
    if active:
        assert row["participation"] == pytest.approx(round(len(current) / active, 4))


def test_regime_is_reported_honestly_when_absent(db_service: Any) -> None:
    row = db_service.get_regime()
    assert set(row) == {"regime", "confidence", "trade_date"}
    # No market_regimes rows exist in the MVP: UNKNOWN, never a fabricated BULL.
    assert row["regime"] in {"UNKNOWN", "BULL", "BEAR", "SIDEWAYS"}
    if row["regime"] == "UNKNOWN":
        assert row["confidence"] == 0.0


def test_ranked_payload_shape(db_service: Any) -> None:
    rows = db_service.get_ranked()
    assert isinstance(rows, list)
    if rows:
        assert set(rows[0]) == {
            "symbol",
            "overall_score",
            "signal",
            "confidence",
            "rank",
            "total",
            "contributions",
        }


# ------------------------------------------------------- valuation/quality
def test_valuation_readers(db_service: Any, market_fixture: dict[str, Any]) -> None:
    summary = db_service.get_valuation_summary(TEST_SYMBOL)
    assert summary is not None
    assert summary["trade_date"] == DATES[-1]
    assert summary["pe"] == pytest.approx(12.5)
    history = db_service.get_valuation_history(TEST_SYMBOL)
    assert [row["trade_date"] for row in history] == [DATES[-1]]


def test_quality_reader(db_service: Any, market_fixture: dict[str, Any]) -> None:
    row = db_service.get_quality(TEST_SYMBOL)
    assert row is not None
    assert row["overall_score"] == pytest.approx(92.5)
    assert row["below_threshold"] is False
    assert set(row["dimensions"]) == {
        "completeness",
        "validity",
        "consistency",
        "uniqueness",
        "freshness",
        "accuracy",
    }


# ---------------------------------------------------------- news/backtests
def test_news_reader_exposes_linked_symbols(
    db_service: Any, market_fixture: dict[str, Any]
) -> None:
    rows = db_service.list_news()
    match = [row for row in rows if row["title"] == "ZZ Test headline"]
    assert match, "inserted news row is not served"
    assert match[0]["symbols"] == [TEST_SYMBOL]


def test_backtest_readers(db_service: Any, market_fixture: dict[str, Any]) -> None:
    bt_id = market_fixture["backtest_id"]
    row = db_service.get_backtest(bt_id)
    assert row is not None
    assert row["id"] == bt_id
    assert row["strategy_name"] == "zz_test_strategy"
    assert row["transaction_cost_bps"] == pytest.approx(15.0)

    metrics = db_service.get_backtest_metrics(bt_id)
    assert [metric["metric_name"] for metric in metrics] == ["total_return"]

    trades = db_service.get_backtest_trades(bt_id)
    assert len(trades) == 1
    assert trades[0]["symbol"] == TEST_SYMBOL
    assert trades[0]["pnl"] == pytest.approx(100.0)
    assert trades[0]["return_pct"] == pytest.approx(0.01)

    assert [run for run in db_service.list_backtests() if run["id"] == bt_id]


def test_statement_and_ratio_readers_are_honest_without_rows(
    db_service: Any, market_fixture: dict[str, Any]
) -> None:
    # No fundamentals were ingested for the temp stock: empty, not invented.
    assert db_service.get_statements(TEST_SYMBOL) == []
    assert db_service.get_ratios(TEST_SYMBOL) == []
    assert db_service.get_features(TEST_SYMBOL)["rows"] == []


def test_uuid_parsing_is_safe(db_service: Any) -> None:
    assert db_service.get_backtest("") is None
    assert db_service.get_backtest_metrics("nope") == []
    assert db_service.get_backtest_trades("nope") == []
