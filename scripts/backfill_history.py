"""Backfill historical market data 2020→now, recompute scores, retrain ML model.

Usage:
    python scripts/backfill_history.py
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import create_engine, select

from apps.api.config import settings
from apps.api.services.db_market import DbMarketService
from src.common.models.reference import Stock
from src.data.pipelines import ingest_eod, ingest_index
from src.data.providers import create_provider, market_provider_chain
from src.ml.feature_dataset import FeatureDatasetBuilder
from src.ml.model_registry import get_default_registry
from src.ml.training import ModelTrainer
from src.quant.scoring.job import compute_and_store_scores

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("dtck.backfill")


def main() -> None:
    engine = create_engine(settings.database_url, pool_pre_ping=True)

    with engine.connect() as conn:
        symbols = sorted([
            row[0] for row in conn.execute(
                select(Stock.symbol).where(Stock.status == "ACTIVE")
            ).all()
        ])

    logger.info("Found %d active symbols to backfill from 2020-01-01", len(symbols))

    start_date = date(2020, 1, 1)
    end_date = date.today()

    # Build provider chain
    chain = market_provider_chain("ssix_finipro")
    logger.info("Provider chain: %s", " -> ".join(chain))

    working_provider = None
    for pid in chain:
        try:
            p = create_provider(pid, universe=frozenset(symbols))
            logger.info("Successfully built provider: %s", pid)
            working_provider = p
            break
        except Exception as exc:
            logger.warning("Could not build provider %s: %s", pid, exc)

    if not working_provider:
        logger.error("No working data provider could be built!")
        return

    # Ingest Index prices first
    logger.info("Ingesting index prices (VNINDEX, VN30)...")
    try:
        res_idx = ingest_index(
            engine, working_provider, ["VNINDEX", "VN30"], start=start_date, end=end_date
        )
        logger.info("Index ingestion result: %s", res_idx.summary())
    except Exception as exc:
        logger.exception("Index ingestion failed: %s", exc)

    # Ingest EOD prices symbol by symbol or in batches
    logger.info(
        "Ingesting EOD prices for %d symbols from %s to %s...", len(symbols), start_date, end_date
    )
    success_count = 0
    fail_count = 0
    for symbol in symbols:
        try:
            res = ingest_eod(engine, working_provider, [symbol], start=start_date, end=end_date)
            if res.rows_written > 0:
                success_count += 1
                logger.info("Symbol %s: written=%d rows", symbol, res.rows_written)
            else:
                logger.warning("Symbol %s: 0 rows written (summary: %s)", symbol, res.summary())
                fail_count += 1
        except Exception as exc:
            fail_count += 1
            logger.error("Symbol %s failed: %s", symbol, exc)

    logger.info("EOD backfill finished: success=%d, failed/empty=%d", success_count, fail_count)

    # Recompute factor scores
    logger.info("Recomputing factor scores across universe...")
    try:
        score_res = compute_and_store_scores(engine)
        logger.info("Scoring result: %s", score_res.summary())
    except Exception as exc:
        logger.exception("Scoring failed: %s", exc)

    # Retrain ML model on DB history
    logger.info("Retraining ML model on DB historical dataset...")
    try:
        db_market = DbMarketService()
        dataset = FeatureDatasetBuilder(horizon_days=5).build(db_market)
        logger.info(
            "ML Dataset built: %d rows, %d features",
            len(dataset.features),
            dataset.features.shape[1],
        )
        registry = get_default_registry()
        trainer = ModelTrainer(horizon_days=5, algorithm="xgboost")
        entry = trainer.train_and_register(dataset, registry)
        logger.info(
            "ML Model successfully trained and registered: %s (version %s)",
            entry.model_id,
            entry.version,
        )

        from src.ml.registry_store import save_entry
        saved = save_entry(engine, entry)
        logger.info("Model saved to DB registry: %s", saved)
    except Exception as exc:
        logger.exception("ML training failed: %s", exc)

    logger.info("Historical backfill and ML retraining completed successfully!")


if __name__ == "__main__":
    main()
