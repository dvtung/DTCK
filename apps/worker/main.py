"""DTCK Worker — schedulers, collectors, daily feature/scoring jobs (Phase 1+).

Schedules periodic tasks via APScheduler (all times Asia/Ho_Chi_Minh):
  1. News Ingestion: Periodic polling (default 15m) from configured provider (e.g. CaféF RSS).
  2. EOD Price + Index Ingestion: after each session close (Mon-Fri 11:30 & 15:30),
     with a stale-only catch-up at 15:50 that repairs a failed close run (KI-014).
  3. Factor Scoring: 30 min after each ingestion (Mon-Fri 12:00 & 16:00) so the
     ranking always reflects the freshest bars.
  4. Email reports: three windows (08:00 previous-session summary, 12:30 morning
     session, 16:30 afternoon session) synced from the database schedule so edits
     made on the dashboard apply without restarting the worker.
"""

from __future__ import annotations

import logging
from contextlib import suppress
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from apps.api.config import parse_codes, parse_cron_hours, settings

logger = logging.getLogger("dtck.worker")

#: Job id of the periodic re-read of the persisted email schedule.
EMAIL_SYNC_JOB_ID = "email_schedule_sync"

#: Job id of the close-of-day retry of the EOD ingestion (KI-014).
EOD_CATCHUP_JOB_ID = "daily_eod_catchup"


def get_engine() -> Engine:
    return create_engine(settings.database_url, pool_pre_ping=True)


def scheduled_news_ingestion() -> None:
    """Fetch recent news from the configured provider and persist + score."""
    from apps.worker.cli import _active_symbols
    from src.data.pipelines import ingest_news
    from src.data.providers import create_provider

    logger.info("Executing scheduled news ingestion (source=%s)", settings.scheduler_news_source)
    try:
        universe = _active_symbols()
        provider = create_provider(settings.scheduler_news_source, universe=frozenset(universe))
        # Fetch news published within the last 2 hours to avoid missing recent bursts
        since = datetime.now(UTC) - timedelta(hours=2)
        engine = get_engine()
        result = ingest_news(
            engine,
            provider,
            since=since,
            threshold=settings.data_quality_threshold,
        )
        logger.info("Scheduled news ingestion finished: %s", result.summary())
    except Exception as exc:
        logger.exception("Scheduled news ingestion failed: %s", exc)


def _session_close_time() -> time:
    """ICT cutoff after which the afternoon session counts as closed."""
    return time(settings.scheduler_session_close_hour, settings.scheduler_session_close_minute)


def expected_session_date(now: datetime | None = None) -> date:
    """Last completed ICT trading date (delegates to :mod:`src.data.freshness`)."""
    from src.data import freshness

    return freshness.expected_session_date(now or datetime.now(UTC), close_at=_session_close_time())


def _log_dataset_freshness(engine: Engine, expected: date, *, context: str) -> list[str]:
    """Log freshness per scheduled dataset; return the stale ones (KI-014).

    Freshness reporting is advisory: a probe failure downgrades to a warning so it
    can never abort an ingestion that already succeeded.
    """
    from src.data import freshness

    try:
        latest = freshness.latest_trade_dates(engine)
    except Exception as exc:  # noqa: BLE001 — advisory probe, never fatal
        logger.warning("%s: could not read dataset freshness: %s", context, exc)
        return []
    stale = freshness.stale_datasets(latest, expected)
    rendered = {name: (value.isoformat() if value else "—") for name, value in latest.items()}
    if stale:
        logger.warning(
            "%s: %s behind the last closed session %s (latest=%s) — rankings, reports and "
            "scores keep using the older rows until an ingestion succeeds",
            context,
            ", ".join(stale),
            expected.isoformat(),
            rendered,
        )
    else:
        logger.info("%s: all scheduled datasets current for %s", context, expected.isoformat())
    return stale


def _ingest_index_bars(
    engine: Engine,
    provider: Any,
    index_codes: tuple[str, ...],
    *,
    start: date,
    end: date,
) -> None:
    """Persist index bars from the provider that just served prices (KI-014).

    Index ingestion used to be a manual CLI step, so ``index_prices`` silently
    lagged the stock universe. It is part of the EOD contract now: a failure is
    logged as an error but never discards the stock bars already written.
    """
    from src.data.pipelines import ingest_index

    if not index_codes:
        return
    if not provider.supports("index_prices"):
        logger.warning(
            "EOD source '%s' does not serve index_prices — %s left unrefreshed",
            provider.id,
            ", ".join(index_codes),
        )
        return
    try:
        result = ingest_index(
            engine,
            provider,
            list(index_codes),
            start=start,
            end=end,
            threshold=settings.data_quality_threshold,
        )
    except Exception as exc:  # noqa: BLE001 — an index failure must not undo prices
        logger.error("Scheduled EOD index ingestion failed (%s): %s", ", ".join(index_codes), exc)
        return
    logger.info("Scheduled EOD index ingestion finished: %s", result.summary())


def scheduled_eod_ingestion(*, only_if_stale: bool = False) -> None:
    """Fetch recent EOD prices (and index bars) for the active universe; persist.

    Runs before the scoring slot so factor scores see same-session bars. The
    lookback window makes the job idempotent: a missed day is recovered on the
    next run and late vendor corrections are picked up.

    Providers are tried in priority order — the configured source first (SSI
    FastConnect by default), then the registry's ``fallback_chains.market``
    (Yahoo, …). A provider that cannot be built (missing credentials) or returns
    no rows is skipped with a log line, so one vendor outage does not leave the
    universe un-scored. ``SCHEDULER_EOD_INDICES`` codes are ingested from the same
    provider when it supports that dataset.

    ``only_if_stale`` turns the run into the close-of-day catch-up: it re-ingests
    only when ``prices``/``index_prices`` are still behind the last closed session.
    """
    from apps.worker.cli import _active_symbols
    from src.data import freshness
    from src.data.pipelines import ingest_eod
    from src.data.providers import create_provider, market_provider_chain

    chain = market_provider_chain(settings.scheduler_eod_source)
    index_codes = parse_codes(settings.scheduler_eod_indices)
    logger.info(
        "Executing scheduled EOD ingestion (chain=%s, lookback=%dd, indices=%s, mode=%s)",
        " → ".join(chain),
        settings.scheduler_eod_lookback_days,
        ",".join(index_codes) or "—",
        "catch-up" if only_if_stale else "scheduled",
    )
    try:
        symbols = sorted(_active_symbols())
        if not symbols:
            logger.warning("No active symbols in the reference universe — skipping EOD ingestion")
            return
        engine = get_engine()
        expected = expected_session_date()
        if only_if_stale and not _log_dataset_freshness(engine, expected, context="EOD catch-up"):
            logger.info("EOD catch-up skipped: datasets already current for %s", expected)
            return
        # SCHEDULER_EOD_INCLUDE_INTRADAY_SESSION keeps the morning run's snapshot
        # (it powers the 12:30 report and is overwritten by the close run);
        # disabling it restricts every run to sessions that have already closed.
        if settings.scheduler_eod_include_intraday_session:
            end = max(freshness.now_ict().date(), expected)
        else:
            end = expected
        start = end - timedelta(days=settings.scheduler_eod_lookback_days)
        for provider_id in chain:
            try:
                provider = create_provider(provider_id)
                result = ingest_eod(
                    engine,
                    provider,
                    symbols,
                    start=start,
                    end=end,
                    threshold=settings.data_quality_threshold,
                )
            except Exception as exc:  # noqa: BLE001 — try the next source instead
                # Credentials are checked lazily (e.g. SSI at token time), so a
                # provider can build fine and fail only on the first request.
                logger.warning("EOD source '%s' failed: %s", provider_id, exc)
                continue
            if result.rows_fetched:
                logger.info("Scheduled EOD ingestion finished: %s", result.summary())
                _ingest_index_bars(engine, provider, index_codes, start=start, end=end)
                _log_dataset_freshness(engine, expected, context=f"EOD ingestion ({provider_id})")
                return
            logger.warning("EOD source '%s' returned no rows — trying the next source", provider_id)
        logger.error("Scheduled EOD ingestion failed: no provider in %s returned rows", chain)
        _log_dataset_freshness(engine, expected, context="EOD ingestion (all sources failed)")
    except Exception as exc:
        logger.exception("Scheduled EOD ingestion failed: %s", exc)


def scheduled_eod_catchup() -> None:
    """Retry the close-of-day ingestion when a vendor outage lost it (KI-014).

    Scheduled shortly before the afternoon scoring slot (15:50 vs 16:00). On a
    healthy day it costs two ``max(trade_date)`` queries and no vendor traffic; on
    2026-09-29 the 15:30 close run failed (SSI ``502`` on ``Market/AccessToken``
    and every fallback too) and this is what recovers the close before the
    afternoon scoring and the 16:30 report.
    """
    scheduled_eod_ingestion(only_if_stale=True)


def _warn_if_scores_are_provisional(engine: Engine) -> None:
    """Warn when the last closed session's bars are missing or still intraday (KI-014).

    The 11:30 run stores the morning snapshot and the close run overwrites it. When
    both the close run and the catch-up fail, scores are computed from that
    snapshot — without this warning the outage reaches rankings and reports
    invisibly, which is exactly what happened on 2026-09-29.
    """
    from src.data import freshness

    trade_date = expected_session_date()
    try:
        ingested_at = freshness.latest_ingested_at(engine, trade_date)
    except Exception as exc:  # noqa: BLE001 — advisory probe, never fatal
        logger.warning("Could not check bar freshness for %s: %s", trade_date, exc)
        return
    close_at = _session_close_time().strftime("%H:%M")
    if ingested_at is None:
        logger.warning(
            "No stock bars stored for the last closed session %s — scores are stale", trade_date
        )
    elif freshness.is_intraday_snapshot(
        ingested_at, trade_date=trade_date, close_at=_session_close_time()
    ):
        logger.warning(
            "Scores for %s use an intraday snapshot (last write %s ICT, session close %s ICT) — "
            "the close-of-day ingestion did not succeed, so rankings and reports are provisional",
            trade_date,
            ingested_at.astimezone(freshness.ICT).strftime("%H:%M"),
            close_at,
        )


def scheduled_scoring_job() -> None:
    """Compute and persist EOD factor scores over fresh prices."""
    from src.quant.factors.scoring import DEFAULT_SCORING_VERSION
    from src.quant.scoring.job import compute_and_store_scores

    logger.info(
        "Executing scheduled EOD factor scoring job (scoring_version=%s)",
        settings.scoring_version,
    )
    try:
        engine = get_engine()
        _warn_if_scores_are_provisional(engine)
        version = settings.scoring_version or DEFAULT_SCORING_VERSION
        result = compute_and_store_scores(engine, scoring_version=version)
        logger.info("Scheduled scoring job finished: %s", result.summary())
    except Exception as exc:
        logger.exception("Scheduled scoring job failed: %s", exc)


def scheduled_email_report(period_label: str = "sáng") -> None:
    """Send automated market overview email report to active subscribers."""
    from apps.api.dependencies import get_market_service
    from src.notifications.service import NotificationService

    logger.info("Executing scheduled email report (%s)", period_label)
    try:
        notif_svc = NotificationService()
        sched = notif_svc.get_schedule_config()
        if not sched.get("is_enabled", True):
            logger.info("Email report schedule is currently disabled — skipping")
            return

        m_svc = get_market_service()
        subject = (
            f"[DTCK] Báo Cáo Tổng Quan Thị Trường Phiên {period_label.title()}"
            f" — {datetime.now(UTC).strftime('%d/%m/%Y')}"
        )
        res = notif_svc.dispatch_report(m_svc, subject=subject)
        logger.info(
            "Scheduled email report (%s) finished: sent=%s/%s",
            period_label,
            res.get("sent", 0),
            res.get("total", 0),
        )
    except Exception as exc:
        logger.exception("Scheduled email report (%s) failed: %s", period_label, exc)


def read_email_schedule() -> dict[str, Any]:
    """Return the persisted email schedule, falling back to the documented default.

    The worker must never crash because the database is unreachable: a missing
    row, a closed connection or a schema without the noon columns all resolve to
    ``DEFAULT_EMAIL_SCHEDULE`` (08:00 / 12:30 / 16:30, Mon–Fri, enabled).
    """
    from src.notifications.service import DEFAULT_EMAIL_SCHEDULE, NotificationService

    try:
        sched = NotificationService().get_schedule_config()
    except Exception as exc:  # pragma: no cover - defensive: DB down at startup
        logger.warning(
            "Cannot read the email schedule from the database (%s) — using defaults", exc
        )
        sched = {}
    merged = dict(DEFAULT_EMAIL_SCHEDULE)
    merged.update({k: v for k, v in (sched or {}).items() if v is not None})
    return merged


def sync_email_schedule_jobs(scheduler: BlockingScheduler) -> dict[str, Any]:
    """(Re)register the three report jobs from the database schedule.

    Called once at startup and then periodically by ``email_schedule_sync`` so a
    schedule saved on the dashboard takes effect on the running worker.  Returns
    the applied schedule (useful for logging and tests).
    """
    from src.notifications.service import REPORT_WINDOWS

    sched = read_email_schedule()
    days = str(sched.get("days_of_week") or "mon-fri")
    applied: dict[str, Any] = {}

    for period, label, hour_key, minute_key in REPORT_WINDOWS:
        hour = int(sched.get(hour_key, 0) or 0)
        minute = int(sched.get(minute_key, 0) or 0)
        job_id = f"daily_{period}_email_report"
        # Drop any previous registration first: `replace_existing` only dedupes
        # jobs that already live in the job store, so an un-started scheduler
        # would otherwise keep both the old and the new trigger.
        with suppress(JobLookupError):
            scheduler.remove_job(job_id)
        scheduler.add_job(
            scheduled_email_report,
            trigger=CronTrigger(
                day_of_week=days,
                hour=hour,
                minute=minute,
                timezone="Asia/Ho_Chi_Minh",
            ),
            args=[label],
            id=job_id,
            name=f"Daily {period.title()} Market Email Report",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        applied[job_id] = f"{hour:02d}:{minute:02d}"
        logger.info(
            "Registered job '%s' cron %s %02d:%02d Asia/Ho_Chi_Minh",
            job_id,
            days,
            hour,
            minute,
        )

    if not sched.get("is_enabled", True):
        logger.info("Email report schedule is disabled — jobs stay registered but will no-op")

    logger.info("Email report schedule synced from the database: %s", applied)
    return applied


def _build_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone="Asia/Ho_Chi_Minh")
    logger.info("Worker scheduler initialized (timezone=Asia/Ho_Chi_Minh)")
    logger.info(
        "scoring_version=%s database_url=%s qdrant_url=%s jobs_enabled=%s",
        settings.scoring_version,
        settings.database_url,
        settings.qdrant_url,
        settings.scheduler_jobs_enabled,
    )

    if settings.scheduler_jobs_enabled:
        # 1. Periodic news polling (e.g. every 15 minutes)
        scheduler.add_job(
            scheduled_news_ingestion,
            trigger=IntervalTrigger(
                minutes=settings.scheduler_news_interval_minutes,
                timezone="Asia/Ho_Chi_Minh",
            ),
            id="periodic_news_ingestion",
            name="Periodic News Ingestion",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info(
            "Registered job 'periodic_news_ingestion' every %d minutes",
            settings.scheduler_news_interval_minutes,
        )

        # 2. Session-close EOD ingestion (Mon-Fri 11:30 & 15:30 Asia/Ho_Chi_Minh)
        eod_hours = parse_cron_hours(settings.scheduler_eod_cron_hours, (11, 15))
        scheduler.add_job(
            scheduled_eod_ingestion,
            trigger=CronTrigger(
                day_of_week="mon-fri",
                hour=",".join(str(h) for h in eod_hours),
                minute=settings.scheduler_eod_cron_minute,
                timezone="Asia/Ho_Chi_Minh",
            ),
            id="daily_eod_ingestion",
            name="Session-Close EOD Price Ingestion",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info(
            "Registered job 'daily_eod_ingestion' cron Mon-Fri %s:%02d Asia/Ho_Chi_Minh",
            "/".join(f"{h:02d}" for h in eod_hours),
            settings.scheduler_eod_cron_minute,
        )

        # 2b. Close-of-day catch-up (15:50): re-runs the ingestion only when the
        #     datasets are still behind the last closed session, so a vendor outage
        #     at 15:30 is repaired before the 16:00 scoring and 16:30 report (KI-014).
        scheduler.add_job(
            scheduled_eod_catchup,
            trigger=CronTrigger(
                day_of_week="mon-fri",
                hour=settings.scheduler_eod_catchup_hour,
                minute=settings.scheduler_eod_catchup_minute,
                timezone="Asia/Ho_Chi_Minh",
            ),
            id=EOD_CATCHUP_JOB_ID,
            name="Close-of-Day EOD Catch-Up",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info(
            "Registered job '%s' cron Mon-Fri %02d:%02d Asia/Ho_Chi_Minh "
            "(ingests only when prices/index_prices are stale)",
            EOD_CATCHUP_JOB_ID,
            settings.scheduler_eod_catchup_hour,
            settings.scheduler_eod_catchup_minute,
        )

        # 3. Session scoring, 30 min after each ingestion (Mon-Fri 12:00 & 16:00)
        scoring_hours = parse_cron_hours(settings.scheduler_scoring_cron_hours, (12, 16))
        scheduler.add_job(
            scheduled_scoring_job,
            trigger=CronTrigger(
                day_of_week="mon-fri",
                hour=",".join(str(h) for h in scoring_hours),
                minute=settings.scheduler_scoring_cron_minute,
                timezone="Asia/Ho_Chi_Minh",
            ),
            id="daily_eod_scoring",
            name="Session Factor Scoring",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info(
            "Registered job 'daily_eod_scoring' cron Mon-Fri %s:%02d Asia/Ho_Chi_Minh",
            "/".join(f"{h:02d}" for h in scoring_hours),
            settings.scheduler_scoring_cron_minute,
        )

        # 4. Email report windows (08:00 / 12:30 / 16:30) read from the database
        #    config, so a dashboard change takes effect without a rebuild.
        sync_email_schedule_jobs(scheduler)

        # 5. Re-read the persisted schedule so edits apply while the worker runs.
        scheduler.add_job(
            lambda: sync_email_schedule_jobs(scheduler),
            trigger=IntervalTrigger(
                minutes=settings.scheduler_email_sync_minutes,
                timezone="Asia/Ho_Chi_Minh",
            ),
            id=EMAIL_SYNC_JOB_ID,
            name="Email Report Schedule Sync",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info(
            "Registered job '%s' every %d minutes (email schedule hot-reload)",
            EMAIL_SYNC_JOB_ID,
            settings.scheduler_email_sync_minutes,
        )

    return scheduler


def run() -> None:
    """Console entry point: `dtck-worker`."""
    logging.basicConfig(level=settings.log_level.upper())
    scheduler = _build_scheduler()
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Worker stopped")


if __name__ == "__main__":
    run()
