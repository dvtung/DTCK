"""Scoring job against the database (W1b): persisted rows are served by the API reader.

Uses a dedicated scoring version so the test's rows can be removed afterwards
without touching a real ``baseline_1.0`` run.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.common.models.quant import FactorScore

TEST_VERSION = "integration_test_1.0"


@pytest.fixture
def scored_run(session: Session, db_ready: None) -> Iterator[Any]:
    """Run the job with the test scoring version; delete its rows afterwards."""
    from apps.api.db import get_engine
    from src.quant.scoring.job import compute_and_store_scores

    result = compute_and_store_scores(get_engine(), scoring_version=TEST_VERSION)
    if result.scored == 0:
        pytest.skip("no prices for the latest trade date — run `ingest --source fixture` first")
    try:
        yield result
    finally:
        session.execute(delete(FactorScore).where(FactorScore.scoring_version == TEST_VERSION))
        session.commit()


def test_job_scores_every_fresh_symbol(scored_run: Any) -> None:
    assert scored_run.trade_date is not None
    assert scored_run.scored > 0
    # Only price-derived dimensions are available without fundamentals.
    assert set(scored_run.dimensions) == {"technical", "momentum", "risk"}


def test_persisted_rows_have_one_dimension_per_column(session: Session, scored_run: Any) -> None:
    rows = list(
        session.scalars(
            select(FactorScore).where(FactorScore.scoring_version == TEST_VERSION).limit(5)
        )
    )
    assert rows
    for row in rows:
        assert row.technical_score is not None
        assert row.momentum_score is not None
        assert row.risk_score is not None
        # Not ingested yet ⇒ NULL, not zero/fabricated.
        assert row.fundamental_score is None
        assert row.valuation_score is None
        assert row.quality_score is None
        assert row.overall_score is not None
        assert row.trade_date == scored_run.trade_date


def test_scoring_is_idempotent(session: Session, scored_run: Any) -> None:
    """Re-running the job must update, not duplicate (PK stock/date/version)."""
    from apps.api.db import get_engine
    from src.quant.scoring.job import compute_and_store_scores

    before = session.scalar(
        select(FactorScore.overall_score)
        .where(FactorScore.scoring_version == TEST_VERSION)
        .order_by(FactorScore.stock_id.asc())
        .limit(1)
    )
    compute_and_store_scores(get_engine(), scoring_version=TEST_VERSION)
    session.expire_all()
    after = session.scalar(
        select(FactorScore.overall_score)
        .where(FactorScore.scoring_version == TEST_VERSION)
        .order_by(FactorScore.stock_id.asc())
        .limit(1)
    )
    rows = list(
        session.scalars(select(FactorScore).where(FactorScore.scoring_version == TEST_VERSION))
    )
    assert rows, "the second run must not delete rows"
    assert after == before


def test_api_reader_serves_the_persisted_run(
    monkeypatch: pytest.MonkeyPatch, scored_run: Any
) -> None:
    """The DB read path ranks whatever the job persisted, with explainability."""
    from apps.api.config import settings
    from apps.api.services.db_market import DbMarketService

    monkeypatch.setattr(settings, "scoring_version", TEST_VERSION)
    ranked = DbMarketService().get_ranked()
    assert len(ranked) == scored_run.scored
    top = ranked[0]
    assert top["rank"] == 1 and top["total"] == len(ranked)
    assert top["overall_score"] is not None
    # Contributions are renormalized over the available dimensions only.
    share = sum(c["contribution_pct"] or 0.0 for c in top["contributions"])
    assert share == pytest.approx(1.0, abs=1e-6)
    assert {c["factor"] for c in top["contributions"]} <= {"technical", "momentum", "risk"}
