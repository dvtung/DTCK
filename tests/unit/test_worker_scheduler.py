"""Unit tests for worker scheduler and background jobs (apps/worker/main.py)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.api.config import parse_codes, parse_cron_hours
from apps.worker.main import (
    EOD_CATCHUP_JOB_ID,
    _build_scheduler,
    read_email_schedule,
    scheduled_eod_catchup,
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
    assert EOD_CATCHUP_JOB_ID in job_ids
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


@patch("src.data.pipelines.ingest_index")
@patch("src.data.pipelines.ingest_eod")
@patch("src.data.providers.create_provider")
@patch("apps.worker.main.get_engine")
@patch("apps.worker.cli._active_symbols")
def test_scheduled_eod_ingestion_executes(
    mock_symbols, mock_engine, mock_create_provider, mock_ingest_eod,  # type: ignore[no-untyped-def]
    mock_ingest_index,  # type: ignore[no-untyped-def]
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


@patch("src.data.pipelines.ingest_index")
@patch("src.data.pipelines.ingest_eod")
@patch("src.data.providers.create_provider")
@patch("apps.worker.main.get_engine")
@patch("apps.worker.cli._active_symbols")
def test_scheduled_eod_ingestion_falls_back_when_the_primary_is_unusable(
    mock_symbols, mock_engine, mock_create_provider, mock_ingest_eod,  # type: ignore[no-untyped-def]
    mock_ingest_index,  # type: ignore[no-untyped-def]
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


@patch("src.data.pipelines.ingest_index")
@patch("src.data.pipelines.ingest_eod")
@patch("src.data.providers.create_provider")
@patch("apps.worker.main.get_engine")
@patch("apps.worker.cli._active_symbols")
def test_scheduled_eod_ingestion_falls_back_when_fetch_itself_raises(
    mock_symbols, mock_engine, mock_create_provider, mock_ingest_eod,  # type: ignore[no-untyped-def]
    mock_ingest_index,  # type: ignore[no-untyped-def]
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


@patch("src.data.pipelines.ingest_index")
@patch("src.data.pipelines.ingest_eod")
@patch("src.data.providers.create_provider")
@patch("apps.worker.main.get_engine")
@patch("apps.worker.cli._active_symbols")
def test_scheduled_eod_ingestion_falls_back_when_the_primary_returns_no_rows(
    mock_symbols, mock_engine, mock_create_provider, mock_ingest_eod,  # type: ignore[no-untyped-def]
    mock_ingest_index,  # type: ignore[no-untyped-def]
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


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("VNINDEX,VN30", ("VNINDEX", "VN30")),
        ("vnindex, vn30 ", ("VNINDEX", "VN30")),
        ("VNINDEX;VN30;VNINDEX", ("VNINDEX", "VN30")),
        ("", ()),
        ("   ", ()),
    ],
)
def test_parse_codes(raw: str, expected: tuple[str, ...]) -> None:
    assert parse_codes(raw) == expected


def test_eod_catchup_runs_before_the_afternoon_scoring_slot() -> None:
    """A failed 15:30 close must be repaired before the 16:00 scoring (KI-014)."""
    from apps.api.config import Settings, settings

    defaults = {name: field.default for name, field in Settings.model_fields.items()}
    assert defaults["scheduler_eod_catchup_hour"] == 15
    assert defaults["scheduler_eod_catchup_minute"] == 50
    assert defaults["scheduler_eod_indices"] == "VNINDEX,VN30"
    assert defaults["scheduler_eod_include_intraday_session"] is True

    jobs = {j.id: j for j in _build_scheduler().get_jobs()}
    catchup = str(jobs[EOD_CATCHUP_JOB_ID].trigger)
    score = str(jobs["daily_eod_scoring"].trigger)
    catchup_minutes = (
        settings.scheduler_eod_catchup_hour * 60 + settings.scheduler_eod_catchup_minute
    )
    last_score_hour = max(parse_cron_hours(settings.scheduler_scoring_cron_hours, (12, 16)))
    score_minutes = last_score_hour * 60 + settings.scheduler_scoring_cron_minute
    assert catchup_minutes < score_minutes
    assert f"hour='{settings.scheduler_eod_catchup_hour}'" in catchup
    assert f"minute='{settings.scheduler_eod_catchup_minute}'" in catchup
    assert "day_of_week='mon-fri'" in catchup and "day_of_week='mon-fri'" in score


@patch("src.data.pipelines.ingest_index")
@patch("src.data.pipelines.ingest_eod")
@patch("src.data.providers.create_provider")
@patch("apps.worker.main.get_engine")
@patch("apps.worker.cli._active_symbols")
def test_eod_ingestion_refreshes_the_configured_indices(
    mock_symbols, mock_engine, mock_create_provider, mock_ingest_eod,  # type: ignore[no-untyped-def]
    mock_ingest_index,  # type: ignore[no-untyped-def]
) -> None:
    """``index_prices`` must be ingested by the same job as the stock bars (KI-014)."""
    from apps.api.config import settings

    mock_symbols.return_value = {"FPT"}
    provider = MagicMock()
    provider.supports.return_value = True
    provider.id = "ssix_finipro"
    mock_create_provider.return_value = provider
    mock_ingest_eod.return_value = IngestResult(
        dataset="prices", source="ssix_finipro", rows_fetched=2, rows_written=2
    )
    mock_ingest_index.return_value = IngestResult(
        dataset="index_prices", source="ssix_finipro", rows_fetched=2, rows_written=2
    )

    scheduled_eod_ingestion()

    assert mock_ingest_index.call_count == 1
    args, kwargs = mock_ingest_index.call_args
    assert args[2] == list(parse_codes(settings.scheduler_eod_indices))
    assert kwargs["start"] <= kwargs["end"]
    # The same provider serves both datasets — no second build.
    assert mock_create_provider.call_count == 1


@patch("src.data.pipelines.ingest_index")
@patch("src.data.pipelines.ingest_eod")
@patch("src.data.providers.create_provider")
@patch("apps.worker.main.get_engine")
@patch("apps.worker.cli._active_symbols")
def test_eod_ingestion_skips_indices_when_the_provider_cannot_serve_them(
    mock_symbols, mock_engine, mock_create_provider, mock_ingest_eod,  # type: ignore[no-untyped-def]
    mock_ingest_index,  # type: ignore[no-untyped-def]
) -> None:
    """A price-only provider (Yahoo) must not be asked for index bars."""
    mock_symbols.return_value = {"FPT"}
    provider = MagicMock()
    provider.supports.return_value = False
    provider.id = "yahoo"
    mock_create_provider.return_value = provider
    mock_ingest_eod.return_value = IngestResult(
        dataset="prices", source="yahoo", rows_fetched=2, rows_written=2
    )

    scheduled_eod_ingestion()

    assert mock_ingest_index.call_count == 0


@patch("src.data.pipelines.ingest_index")
@patch("src.data.pipelines.ingest_eod")
@patch("src.data.providers.create_provider")
@patch("apps.worker.main.get_engine")
@patch("apps.worker.cli._active_symbols")
def test_eod_catchup_ingests_only_when_a_dataset_is_stale(
    mock_symbols, mock_engine, mock_create_provider, mock_ingest_eod,  # type: ignore[no-untyped-def]
    mock_ingest_index,  # type: ignore[no-untyped-def]
) -> None:
    """The 15:50 catch-up is a no-op on a healthy day and a repair when not (KI-014)."""
    from datetime import date

    mock_symbols.return_value = {"FPT"}
    expected = date(2026, 9, 29)

    with patch("apps.worker.main.expected_session_date", return_value=expected):
        # Fresh: prices + index_prices both at the last closed session.
        with patch(
            "src.data.freshness.latest_trade_dates",
            return_value={"prices": expected, "index_prices": expected},
        ):
            scheduled_eod_catchup()
        assert mock_ingest_eod.call_count == 0
        assert mock_create_provider.call_count == 0

        # The 2026-09-29 outage shape: indices (and prices) behind → repair both.
        provider = MagicMock()
        provider.supports.return_value = True
        provider.id = "ssix_finipro"
        mock_create_provider.return_value = provider
        mock_ingest_eod.return_value = IngestResult(
            dataset="prices", source="ssix_finipro", rows_fetched=1, rows_written=1
        )
        mock_ingest_index.return_value = IngestResult(
            dataset="index_prices", source="ssix_finipro", rows_fetched=1, rows_written=1
        )
        with patch(
            "src.data.freshness.latest_trade_dates",
            return_value={"prices": expected, "index_prices": date(2026, 9, 25)},
        ):
            scheduled_eod_catchup()
        assert mock_ingest_eod.call_count == 1
        assert mock_ingest_index.call_count == 1


def _scoring_job_with_bar_written_at(
    written_at: str, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> str:
    """Run the scoring job with a stubbed newest write time; return the log text."""
    from datetime import datetime, time

    from apps.worker.main import expected_session_date, scheduled_scoring_job
    from src.data.freshness import ICT

    trade_date = expected_session_date()
    hour, minute = (int(part) for part in written_at.split(":"))
    ingested_at = datetime.combine(trade_date, time(hour, minute), tzinfo=ICT)
    summary = MagicMock()
    summary.summary.return_value = f"scores trade_date={trade_date} scored=136"

    monkeypatch.setattr("apps.worker.main.get_engine", lambda: MagicMock())
    monkeypatch.setattr(
        "src.data.freshness.latest_ingested_at",
        lambda _engine, _trade_date: ingested_at,
    )
    with patch("src.quant.scoring.job.compute_and_store_scores", return_value=summary):
        with caplog.at_level("WARNING", logger="dtck.worker"):
            scheduled_scoring_job()
    return "\n".join(record.getMessage() for record in caplog.records)


def test_scoring_job_warns_when_scores_use_an_intraday_snapshot(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Silently re-scoring the 11:30 snapshot is what hid the 2026-09-29 outage (KI-014)."""
    logged = _scoring_job_with_bar_written_at("11:30", monkeypatch, caplog)
    assert "intraday snapshot" in logged


def test_scoring_job_is_quiet_when_the_close_was_ingested(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    logged = _scoring_job_with_bar_written_at("15:35", monkeypatch, caplog)
    assert "intraday snapshot" not in logged
