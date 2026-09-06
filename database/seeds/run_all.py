"""Run all reference-data seeds (exchanges, sectors, VN30 membership …).

Usage:
    docker compose exec api python -m database.seeds.run_all
"""

from __future__ import annotations

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dtck.seeds")


def run_all() -> None:
    # Phase-0 scaffold: seed modules register here from T003 onward.
    # Example: seed_exchanges()  -> exchanges (HOSE/HNX/UPCOM)
    #          seed_sectors()    -> sector/industry taxonomy
    #          seed_universe()   -> VN30/VN100 membership
    logger.info("No seeds implemented yet — expected until T003 (migrations+seeds).")


if __name__ == "__main__":
    run_all()
