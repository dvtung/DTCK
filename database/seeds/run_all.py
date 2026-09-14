"""Run all reference-data seeds (exchanges, sectors, VN30 membership …).

Idempotent — safe to run repeatedly.

Usage:
    docker compose exec api python -m database.seeds.run_all
    python -m database.seeds.run_all    # requires DATABASE_URL (see helper/deployment.md)
"""

from __future__ import annotations

import logging

from database.seeds._core import get_engine
from database.seeds.seed_exchanges import seed_exchanges
from database.seeds.seed_sectors import seed_sectors
from database.seeds.seed_vn30 import seed_vn30

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dtck.seeds")


def run_all() -> dict[str, int]:
    """Run every seed within a single transaction; return row counts."""
    engine = get_engine()
    counts: dict[str, int] = {}
    with engine.begin() as conn:
        exchanges = seed_exchanges(conn)
        counts["exchanges"] = len(exchanges)
        logger.info("seeded %d exchanges", len(exchanges))

        sector_ids, industry_ids = seed_sectors(conn)
        counts["sectors"] = len(sector_ids)
        counts["industries"] = len(industry_ids)
        logger.info("seeded %d sectors, %d industries", len(sector_ids), len(industry_ids))

        vn30 = seed_vn30(conn, exchanges, sector_ids, industry_ids)
        counts["vn30"] = vn30
        logger.info("seeded %d VN30 constituent rows", vn30)

    return counts


if __name__ == "__main__":
    run_all()
