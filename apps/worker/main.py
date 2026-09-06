"""DTCK Worker — schedulers, collectors, daily feature/scoring jobs (Phase 1+).

Phase-0 scaffold: starts an APScheduler instance without registered jobs.
Jobs are registered incrementally with the Data Foundation (Phase 1).
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from apps.api.config import settings

logger = logging.getLogger("dtck.worker")


def _build_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone="Asia/Ho_Chi_Minh")
    logger.info("Worker started (scaffold — no jobs registered yet)")
    logger.info(
        "scoring_version=%s database_url=%s qdrant_url=%s",
        settings.scoring_version,
        settings.database_url,
        settings.qdrant_url,
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
