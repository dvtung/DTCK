"""Unit tests for worker scheduler and background jobs (apps/worker/main.py)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.api.config import parse_cron_hours
from apps.worker.main import (
    _build_scheduler,
    read_email_schedule,
    scheduled_eod_ingestion,
    scheduled_news_ingestion,
    scheduled_scoring_job,
    sync_email_schedule_jobs,
)
from src.data.pipelines import IngestResult


@pytest.fixture(autouse=True)
def _offline_email_schedule(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scheduler unit tests must not need a database to resolve the email schedule.

    ``read_email_schedule`` is replaced on the module so the already-imported
    reference in this file still exercises the real fallback path.
    """
    from src.notifications.service import DEFAULT_EMAIL_SCHEDULE

    monkeypatch.setattr(
        "apps.worker.main.read_email_schedule", lambda: dict(DEFAULT_EMAIL_SCHEDULE)
    )


def test_worker_scheduler_registers_jobs() -> None:
    scheduler = _build_scheduler()
    jobs = scheduler.get_jobs()
    job_ids = {j.id for j in jobs}
    assert "periodic_news_ingestion" in job_ids
    assert "daily_eod_ingestion" in job_ids
    assert "daily_eod_scoring" in job_ids
    assert "daily_morning_email_report" in job_ids
    assert "daily_noon_email_report" in job_ids
    assert "daily_afternoon_email_report" in job_ids
    assert "email_schedule_sync" in job_ids


def test_eod_ingestion_is_scheduled_before_scoring() -> None:
    """Every ingestion slot must land ahead of the matching scoring slot."""
    from apps.api.config import settings

    ingest_hours = parse_cron_hours(settings.scheduler_eod_cron_hours, (11, 15))
    score_hours = parse_cron_hours(settings.scheduler_scoring_cron_hours, (12, 16))
    ingest = next(j for j in _build_scheduler().get_jobs() if j.id == "daily_eod_ingestion")
    score = next(j for j in _build_scheduler().get_jobs() if j.id == "daily_eod_scoring")

    assert len(ingest_hours) == len(score_hours) >= 2
    for ingest_hour, score_hour in zip(ingest_hours, score_hours, strict=True):
        ingest_minute = (ingest_hour * 60) + settings.scheduler_eod_cron_minute
        score_minute = (score_hour * 60) + settings.scheduler_scoring_cron_minute
        assert ingest_minute < score_minute
    assert ingest.trigger.timezone is None or str(ingest.trigger.timezone) == "Asia/Ho_Chi_Minh"
    assert score.trigger.timezone is None or str(score.trigger.timezone) == "Asia/Ho_Chi_Minh"


def test_session_crons_use_the_two_trading_sessions() -> None:
    """Documented defaults: ingest 11:30 & 15:30, score 12:00 & 16:00 (ICT)."""
    from apps.api.config import Settings, settings

    defaults = {name: field.default for name, field in Settings.model_fields.items()}
    assert defaults["scheduler_eod_cron_hours"] == "11,15"
    assert defaults["scheduler_eod_cron_minute"] == 30
    assert defaults["scheduler_scoring_cron_hours"] == "12,16"
    assert defaults["scheduler_scoring_cron_minute"] == 0

    jobs = {j.id: j for j in _build_scheduler().get_jobs()}
    ingest = str(jobs["daily_eod_ingestion"].trigger)
    score = str(jobs["daily_eod_scoring"].trigger)
    assert f"hour='{settings.scheduler_eod_cron_hours}'" in ingest
    assert f"minute='{settings.scheduler_eod_cron_minute}'" in ingest
    assert f"hour='{settings.scheduler_scoring_cron_hours}'" in score
    assert f"minute='{settings.scheduler_scoring_cron_minute}'" in score
    assert "day_of_week='mon-fri'" in ingest and "day_of_week='mon-fri'" in score


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("11,15", (11, 15)),
        ("15, 11", (11, 15)),
        ("11;15;11", (11, 15)),
        ("", (11, 15)),
        ("nope", (11, 15)),
        ("11,99", (11,)),
        ("16,12,8", (8, 12, 16)),
    ],
)
def test_parse_cron_hours(raw: str, expected: tuple[int, ...]) -> None:
    assert parse_cron_hours(raw, (11, 15)) == expected


def test_email_report_jobs_follow_the_database_schedule() -> None:
    """A schedule read from the DB must drive the three report cron triggers."""
    scheduler = _build_scheduler()
    stored = {
        "morning_hour": 7,
        "morning_minute": 45,
        "noon_hour": 12,
        "noon_minute": 15,
        "afternoon_hour": 17,
        "afternoon_minute": 0,
        "days_of_week": "mon-fri",
        "is_enabled": True,
    }
    with patch("apps.worker.main.read_email_schedule", return_value=stored):
        applied = sync_email_schedule_jobs(scheduler)

    assert applied == {
        "daily_morning_email_report": "07:45",
        "daily_noon_email_report": "12:15",
        "daily_afternoon_email_report": "17:00",
    }
    trigger = str(
        next(j for j in scheduler.get_jobs() if j.id == "daily_noon_email_report").trigger
    )
    assert "hour='12'" in trigger
    assert "minute='15'" in trigger
    assert "day_of_week='mon-fri'" in trigger

    # A re-sync applies edited values to the already-registered job.
    stored["afternoon_hour"] = 18
    with patch("apps.worker.main.read_email_schedule", return_value=stored):
        resynced = sync_email_schedule_jobs(scheduler)
    assert resynced["daily_afternoon_email_report"] == "18:00"
    assert len([j for j in scheduler.get_jobs() if j.id.endswith("_email_report")]) == 3


def test_read_email_schedule_falls_back_when_the_database_is_down() -> None:
    """An unreachable database must never stop the worker from registering jobs."""
    with patch(
        "src.notifications.service.NotificationService.get_schedule_config",
        side_effect=RuntimeError("db down"),
    ):
        sched = read_email_schedule()
    assert (sched["morning_hour"], sched["morning_minute"]) == (8, 0)
    assert (sched["noon_hour"], sched["noon_minute"]) == (12, 30)
    assert (sched["afternoon_hour"], sched["afternoon_minute"]) == (16, 30)
    assert sched["is_enabled"] is True


def test_scheduled_email_report_uses_the_window_label() -> None:
    from apps.worker.main import scheduled_email_report

    service = MagicMock()
    service.get_schedule_config.return_value = {"is_enabled": True}
    service.dispatch_report.return_value = {"sent": 1, "total": 2}
    with (
        patch("src.notifications.service.NotificationService", return_value=service),
        patch("apps.api.dependencies.get_market_service", return_value=MagicMock()),
    ):
        scheduled_email_report("trưa")

    subject = service.dispatch_report.call_args.kwargs["subject"]
    assert "Trưa" in subject


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


@patch("src.data.pipelines.ingest_eod")
@patch("src.data.providers.create_provider")
@patch("apps.worker.main.get_engine")
@patch("apps.worker.cli._active_symbols")
def test_scheduled_eod_ingestion_falls_back_when_the_primary_is_unusable(
    mock_symbols, mock_engine, mock_create_provider, mock_ingest_eod,  # type: ignore[no-untyped-def]
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """SSI primary without credentials must fall back to Yahoo, not abort the run."""
    from apps.api.config import settings

    monkeypatch.setattr(settings, "scheduler_eod_source", "ssix_finipro")
    mock_symbols.return_value = {"FPT"}
    mock_create_provider.side_effect = [
        ValueError("missing SSI_CONSUMER_ID or SSI_CONSUMER_SECRET"),
        MagicMock(),
    ]
    mock_ingest_eod.return_value = IngestResult(
        dataset="prices", source="yahoo", rows_fetched=3, rows_written=3
    )

    scheduled_eod_ingestion()

    attempted = [c.args[0] for c in mock_create_provider.call_args_list]
    assert attempted == ["ssix_finipro", "yahoo"]
    assert mock_ingest_eod.call_count == 1


@patch("src.data.pipelines.ingest_eod")
@patch("src.data.providers.create_provider")
@patch("apps.worker.main.get_engine")
@patch("apps.worker.cli._active_symbols")
def test_scheduled_eod_ingestion_falls_back_when_fetch_itself_raises(
    mock_symbols, mock_engine, mock_create_provider, mock_ingest_eod,  # type: ignore[no-untyped-def]
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """Credentials are checked lazily: SSI builds fine but raises at token
    time inside ``ingest_eod`` — the chain must still reach Yahoo (bug found
    live during T015 hardening)."""
    from apps.api.config import settings

    monkeypatch.setattr(settings, "scheduler_eod_source", "ssix_finipro")
    mock_symbols.return_value = {"FPT"}
    mock_create_provider.side_effect = [MagicMock(), MagicMock()]
    mock_ingest_eod.side_effect = [
        ValueError("missing SSI_CONSUMER_ID or SSI_CONSUMER_SECRET"),
        IngestResult(dataset="prices", source="yahoo", rows_fetched=3, rows_written=3),
    ]

    scheduled_eod_ingestion()

    attempted = [c.args[0] for c in mock_create_provider.call_args_list]
    assert attempted == ["ssix_finipro", "yahoo"]
    assert mock_ingest_eod.call_count == 2


@patch("src.data.pipelines.ingest_eod")
@patch("src.data.providers.create_provider")
@patch("apps.worker.main.get_engine")
@patch("apps.worker.cli._active_symbols")
def test_scheduled_eod_ingestion_falls_back_when_the_primary_returns_no_rows(
    mock_symbols, mock_engine, mock_create_provider, mock_ingest_eod,  # type: ignore[no-untyped-def]
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """An empty batch from the primary is a failure signal, not a silent no-op."""
    from apps.api.config import settings

    monkeypatch.setattr(settings, "scheduler_eod_source", "ssix_finipro")
    mock_symbols.return_value = {"FPT"}
    mock_create_provider.return_value = MagicMock()
    mock_ingest_eod.side_effect = [
        IngestResult(dataset="prices", source="ssix_finipro", rows_fetched=0),
        IngestResult(dataset="prices", source="yahoo", rows_fetched=3, rows_written=3),
    ]

    scheduled_eod_ingestion()

    assert mock_ingest_eod.call_count == 2
    assert [c.args[0] for c in mock_create_provider.call_args_list] == [
        "ssix_finipro",
        "yahoo",
    ]
