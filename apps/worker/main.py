"""DTCK Worker — schedulers, collectors, daily feature/scoring jobs (Phase 1+).

Schedules periodic tasks via APScheduler:
  1. News Ingestion: Periodic polling (default 15m) from configured provider (e.g. CaféF RSS).
  2. EOD Price Ingestion: Daily fetch after market close (Mon-Fri 15:05 Asia/Ho_Chi_Minh).
  3. EOD Factor Scoring: Daily recompute at market close (Mon-Fri 15:30 Asia/Ho_Chi_Minh),
     25 minutes after ingestion so same-day bars are already persisted.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from apps.api.config import settings

logger = logging.getLogger("dtck.worker")


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


def scheduled_eod_ingestion() -> None:
    """Fetch recent EOD prices for the active universe and persist + score.

    Runs before the scoring job (15:05 vs 15:30) so factor scores see same-day
    bars. The lookback window makes the job idempotent: a missed day is
    recovered on the next run and late vendor corrections are picked up.
    """
    from apps.worker.cli import _active_symbols
    from src.data.pipelines import ingest_eod
    from src.data.providers import create_provider

    logger.info(
        "Executing scheduled EOD ingestion (source=%s, lookback=%dd)",
        settings.scheduler_eod_source,
        settings.scheduler_eod_lookback_days,
    )
    try:
        symbols = sorted(_active_symbols())
        if not symbols:
            logger.warning("No active symbols in the reference universe — skipping EOD ingestion")
            return
        provider = create_provider(settings.scheduler_eod_source)
        end = datetime.now(UTC).date()
        start = end - timedelta(days=settings.scheduler_eod_lookback_days)
        engine = get_engine()
        result = ingest_eod(
            engine,
            provider,
            symbols,
            start=start,
            end=end,
            threshold=settings.data_quality_threshold,
        )
        logger.info("Scheduled EOD ingestion finished: %s", result.summary())
    except Exception as exc:
        logger.exception("Scheduled EOD ingestion failed: %s", exc)


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
        version = settings.scoring_version or DEFAULT_SCORING_VERSION
        result = compute_and_store_scores(engine, scoring_version=version)
        logger.info("Scheduled scoring job finished: %s", result.summary())
    except Exception as exc:
        logger.exception("Scheduled scoring job failed: %s", exc)


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

        # 2. Daily EOD price ingestion after market close (Mon-Fri 15:05)
        scheduler.add_job(
            scheduled_eod_ingestion,
            trigger=CronTrigger(
                day_of_week="mon-fri",
                hour=settings.scheduler_eod_cron_hour,
                minute=settings.scheduler_eod_cron_minute,
                timezone="Asia/Ho_Chi_Minh",
            ),
            id="daily_eod_ingestion",
            name="Daily EOD Price Ingestion",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info(
            "Registered job 'daily_eod_ingestion' cron Mon-Fri %02d:%02d Asia/Ho_Chi_Minh",
            settings.scheduler_eod_cron_hour,
            settings.scheduler_eod_cron_minute,
        )

        # 3. Daily EOD factor scoring (Mon-Fri 15:30 Asia/Ho_Chi_Minh)
        scheduler.add_job(
            scheduled_scoring_job,
            trigger=CronTrigger(
                day_of_week="mon-fri",
                hour=settings.scheduler_scoring_cron_hour,
                minute=settings.scheduler_scoring_cron_minute,
                timezone="Asia/Ho_Chi_Minh",
            ),
            id="daily_eod_scoring",
            name="Daily EOD Factor Scoring",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info(
            "Registered job 'daily_eod_scoring' cron Mon-Fri %02d:%02d Asia/Ho_Chi_Minh",
            settings.scheduler_scoring_cron_hour,
            settings.scheduler_scoring_cron_minute,
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
