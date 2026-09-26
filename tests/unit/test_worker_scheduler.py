"""Unit tests for worker scheduler and background jobs (apps/worker/main.py)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from apps.worker.main import (
    _build_scheduler,
    scheduled_eod_ingestion,
    scheduled_news_ingestion,
    scheduled_scoring_job,
)


def test_worker_scheduler_registers_jobs() -> None:
    scheduler = _build_scheduler()
    jobs = scheduler.get_jobs()
    job_ids = {j.id for j in jobs}
    assert "periodic_news_ingestion" in job_ids
    assert "daily_eod_ingestion" in job_ids
    assert "daily_eod_scoring" in job_ids


def test_eod_ingestion_is_scheduled_before_scoring() -> None:
    """Ingestion must run first so scoring sees same-day bars."""
    from apps.api.config import settings

    ingest = next(j for j in _build_scheduler().get_jobs() if j.id == "daily_eod_ingestion")
    score = next(j for j in _build_scheduler().get_jobs() if j.id == "daily_eod_scoring")
    ingest_minute = (settings.scheduler_eod_cron_hour * 60) + settings.scheduler_eod_cron_minute
    score_hour = settings.scheduler_scoring_cron_hour * 60
    score_minute = score_hour + settings.scheduler_scoring_cron_minute
    assert ingest_minute < score_minute
    assert ingest.trigger.timezone is None or str(ingest.trigger.timezone) == "Asia/Ho_Chi_Minh"
    assert score.trigger.timezone is None or str(score.trigger.timezone) == "Asia/Ho_Chi_Minh"


def test_worker_scheduler_can_disable_jobs(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from apps.api.config import settings

    monkeypatch.setattr(settings, "scheduler_jobs_enabled", False)
    scheduler = _build_scheduler()
    assert len(scheduler.get_jobs()) == 0


@patch("src.data.pipelines.ingest_news")
@patch("src.data.providers.create_provider")
@patch("apps.worker.main.get_engine")
def test_scheduled_news_ingestion_executes(
    mock_engine, mock_create_provider, mock_ingest_news  # type: ignore[no-untyped-def]
) -> None:
    mock_res = MagicMock()
    mock_res.summary.return_value = "ingested 5 items"
    mock_ingest_news.return_value = mock_res

    scheduled_news_ingestion()
    assert mock_create_provider.called
    assert mock_ingest_news.called


@patch("src.quant.scoring.job.compute_and_store_scores")
@patch("apps.worker.main.get_engine")
def test_scheduled_scoring_job_executes(mock_engine, mock_compute_scores) -> None:  # type: ignore[no-untyped-def]
    mock_res = MagicMock()
    mock_res.summary.return_value = "scored 10 stocks"
    mock_compute_scores.return_value = mock_res

    scheduled_scoring_job()
    assert mock_compute_scores.called


@patch("src.data.pipelines.ingest_eod")
@patch("src.data.providers.create_provider")
@patch("apps.worker.main.get_engine")
@patch("apps.worker.cli._active_symbols")
def test_scheduled_eod_ingestion_executes(
    mock_symbols, mock_engine, mock_create_provider, mock_ingest_eod  # type: ignore[no-untyped-def]
) -> None:
    mock_symbols.return_value = {"FPT", "VCB"}
    mock_res = MagicMock()
    mock_res.summary.return_value = "prices source=yahoo written=5"
    mock_ingest_eod.return_value = mock_res

    scheduled_eod_ingestion()
    assert mock_create_provider.called
    assert mock_ingest_eod.called
    args, kwargs = mock_ingest_eod.call_args
    assert args[2] == ["FPT", "VCB"]  # sorted universe symbols
    assert kwargs["start"] <= kwargs["end"]


@patch("src.data.pipelines.ingest_eod")
@patch("src.data.providers.create_provider")
@patch("apps.worker.main.get_engine")
@patch("apps.worker.cli._active_symbols")
def test_scheduled_eod_ingestion_skips_empty_universe(
    mock_symbols, mock_engine, mock_create_provider, mock_ingest_eod  # type: ignore[no-untyped-def]
) -> None:
    mock_symbols.return_value = set()
    scheduled_eod_ingestion()
    assert not mock_ingest_eod.called
