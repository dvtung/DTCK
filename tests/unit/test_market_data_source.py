"""Market-data source contract: selection + implementation parity (W1, KI-008).

The API read path is swappable: ``MARKET_DATA_SOURCE=memory`` (default, DB-free)
or ``db|auto`` (TimescaleDB). These tests pin the *contract* — every method the
routers may call exists on both implementations, and the selection honours the
setting — so a router can never be wired to a source that cannot serve it.
"""

from __future__ import annotations

import pytest

from apps.api.services.db_market import DbMarketService
from apps.api.services.market_data import MarketService
from apps.api.services.market_source import MarketSource
from apps.api.services.ranking_payload import to_ranking_payload
from src.quant.scoring.engine import score_universe

# The full surface consumed by apps/api/routers/*, agents and the dashboard.
SOURCE_METHODS = (
    "list_indices",
    "get_index",
    "get_regime",
    "get_breadth",
    "list_stocks",
    "get_stock",
    "get_prices",
    "get_ranking",
    "get_ranked",
    "get_indicators",
    "get_features",
    "get_valuation_summary",
    "get_valuation_history",
    "get_quality",
    "get_statements",
    "get_ratios",
    "list_news",
    "get_backtest",
    "list_backtests",
    "get_backtest_metrics",
    "get_backtest_trades",
)


@pytest.mark.parametrize("implementation", [MarketService, DbMarketService])
def test_source_implements_the_full_contract(implementation: type) -> None:
    missing = [name for name in SOURCE_METHODS if not callable(getattr(implementation, name, None))]
    assert not missing, f"{implementation.__name__} is missing {missing}"


@pytest.mark.parametrize("implementation", [MarketService, DbMarketService])
def test_source_satisfies_the_runtime_protocol(implementation: type) -> None:
    """``MarketSource`` is ``@runtime_checkable``; both sources must pass it."""
    assert isinstance(implementation(), MarketSource)


def test_protocol_lists_every_documented_method() -> None:
    declared = {
        name
        for name in dir(MarketSource)
        if not name.startswith("_") and callable(getattr(MarketSource, name))
    }
    assert declared == set(SOURCE_METHODS)


def test_default_source_is_the_db_free_fixture() -> None:
    from apps.api.config import settings

    assert settings.market_data_source == "memory"


def test_memory_mode_returns_the_fixture_service() -> None:
    from apps.api.dependencies import get_market_service

    get_market_service.cache_clear()
    try:
        assert isinstance(get_market_service(), MarketService)
    finally:
        get_market_service.cache_clear()


def test_db_mode_returns_the_database_service(monkeypatch: pytest.MonkeyPatch) -> None:
    from apps.api import dependencies
    from apps.api.config import settings

    monkeypatch.setattr(settings, "market_data_source", "db")
    dependencies.get_market_service.cache_clear()
    try:
        assert isinstance(dependencies.get_market_service(), DbMarketService)
    finally:
        dependencies.get_market_service.cache_clear()


def test_auto_mode_falls_back_when_the_database_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.api import db as api_db
    from apps.api import dependencies
    from apps.api.config import settings

    monkeypatch.setattr(settings, "market_data_source", "auto")
    # ``database_is_ready`` is imported inside ``get_market_service``, so the
    # patch must target the module it is imported from (apps.api.db).
    monkeypatch.setattr(api_db, "database_is_ready", lambda **_: False)
    dependencies.get_market_service.cache_clear()
    try:
        assert isinstance(dependencies.get_market_service(), MarketService)
    finally:
        dependencies.get_market_service.cache_clear()


def test_ranking_payload_matches_the_api_contract() -> None:
    rankings = score_universe({"FPT": {"technical": 80.0, "valuation": 60.0}})
    payload = to_ranking_payload(rankings[0], 1, len(rankings))
    assert set(payload) == {
        "symbol",
        "overall_score",
        "signal",
        "confidence",
        "rank",
        "total",
        "contributions",
    }
    assert payload["symbol"] == "FPT"
    assert payload["rank"] == 1 and payload["total"] == 1


def test_ranking_payload_contributions_sum_exactly_to_one() -> None:
    """Rounding must not leave 0.9999 — the residual folds into the largest share.

    Live finding (T015b): worst deviation 1e-4 across the ranked universe when
    each ``contribution_pct`` was rounded independently.
    """
    from src.quant.scoring.engine import FactorContribution, ScoreDecomposition, StockRanking

    thirds = [
        FactorContribution(
            factor=name, score=50.0, weight=1 / 3, weighted_score=1 / 3, contribution_pct=1 / 3
        )
        for name in ("technical", "momentum", "risk")
    ]
    ranking = StockRanking(
        stock_id="FPT",
        overall_score=50.0,
        decomposition=ScoreDecomposition(overall_score=50.0, contributions=thirds),
        signal="NEUTRAL",
        confidence=0.5,
    )
    payload = to_ranking_payload(ranking, 1, 1)
    total = sum(c["contribution_pct"] for c in payload["contributions"])
    assert total == pytest.approx(1.0, abs=1e-9)
    # Residual landed on exactly one component (the largest share).
    pcts = sorted(c["contribution_pct"] for c in payload["contributions"])
    assert pcts[0] == 0.3333 and pcts[-1] == 0.3334


def test_ranking_payload_partial_vector_is_untouched() -> None:
    """Shares that do not sum to 1 before rounding are passed through as-is."""
    from src.quant.scoring.engine import FactorContribution, ScoreDecomposition, StockRanking

    parts = [
        FactorContribution(
            factor=name, score=50.0, weight=0.4, weighted_score=0.4, contribution_pct=0.4
        )
        for name in ("technical", "momentum")
    ]
    ranking = StockRanking(
        stock_id="FPT",
        overall_score=50.0,
        decomposition=ScoreDecomposition(overall_score=50.0, contributions=parts),
        signal="NEUTRAL",
        confidence=0.5,
    )
    payload = to_ranking_payload(ranking, 1, 1)
    assert all(c["contribution_pct"] == 0.4 for c in payload["contributions"])
    share = sum(c["contribution_pct"] or 0.0 for c in payload["contributions"])
    assert share == pytest.approx(0.8, abs=1e-6)


def test_ranking_payload_is_identical_for_both_sources() -> None:
    """The DB source and the fixture shape rankings through one helper."""
    from apps.api.services.market_data import MarketService as Fixture

    fixture_rows = Fixture().get_ranked()
    assert fixture_rows, "fixture universe must produce rankings"
    assert all(set(row) == set(fixture_rows[0]) for row in fixture_rows)
