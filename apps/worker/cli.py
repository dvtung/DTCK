"""Worker CLI — one-off operational commands (ingest, backfill, recompute).

Usage:
    # offline (no network, deterministic fixture rows — KI-006)
    python -m apps.worker.cli ingest --dataset prices --source fixture \
        --start 2026-09-01 --end 2026-09-05 --symbols FPT,VCB

    # live provider (requires verified endpoints + credentials; see KI-006/KI-007)
    python -m apps.worker.cli ingest --dataset prices --source vndirect \
        --start 2026-09-01 --end 2026-09-05 --symbols FPT,VCB

    python -m apps.worker.cli ingest --dataset index_prices --source fixture \
        --indexes VNINDEX,VN30 --start 2026-09-01 --end 2026-09-05
    python -m apps.worker.cli ingest --dataset news --source fixture
"""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import create_engine

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

    from src.data.providers.base import DataProvider

logger = logging.getLogger("dtck.worker.cli")


def _parse_date(value: str | None, *, default: date) -> date:
    return date.fromisoformat(value) if value else default


def _build_provider(source: str, args: argparse.Namespace) -> DataProvider:
    """Build the provider named by ``source`` ('fixture' = offline rows)."""
    from src.data.providers import create_provider

    if source == "fixture":
        from src.data.providers.fixture import build_fixture_provider

        return build_fixture_provider(symbols=args.symbols or [], start=args.start, end=args.end)
    return create_provider(source)


def _engine() -> Engine:
    from apps.api.config import settings

    return create_engine(settings.database_url, pool_pre_ping=True)


def run_ingest(args: argparse.Namespace) -> int:
    """Execute one pipeline run and print its summary + quality gate verdict."""
    from src.data.pipelines import ingest_eod, ingest_index, ingest_news

    engine = _engine()
    provider = _build_provider(args.source, args)
    if args.dataset == "prices":
        result = ingest_eod(
            engine, provider, args.symbols, start=args.start, end=args.end, threshold=args.threshold
        )
    elif args.dataset == "index_prices":
        result = ingest_index(
            engine,
            provider,
            args.indexes,
            start=args.start,
            end=args.end,
            threshold=args.threshold,
        )
    elif args.dataset == "news":
        result = ingest_news(engine, provider, since=args.since, threshold=args.threshold)
    else:
        raise ValueError(f"unknown dataset '{args.dataset}'")

    for issue in result.issues:
        logger.warning("validation issue: %s", issue)
    logger.info("%s", result.summary())
    if not result.quality_passed:
        logger.error("quality gate FAILED — dataset flagged below_threshold (§39)")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    today = datetime.now(tz=UTC).date()
    parser = argparse.ArgumentParser(prog="dtck-worker-cli")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="run a data collector pipeline")
    ingest.add_argument("--dataset", default="prices", choices=["prices", "index_prices", "news"])
    ingest.add_argument("--source", default="fixture", help="provider id or 'fixture' (offline)")
    ingest.add_argument("--start", help="window start (YYYY-MM-DD)")
    ingest.add_argument("--end", help="window end (YYYY-MM-DD); default = today")
    ingest.add_argument("--symbols", help="comma-separated tickers for --dataset prices")
    ingest.add_argument("--indexes", help="comma-separated index codes for index_prices")
    ingest.add_argument("--since", help="news: fetch items published after this ISO timestamp")
    ingest.add_argument(
        "--threshold", type=float, help="override the data-quality gate threshold (§39)"
    )
    ingest.set_defaults(
        func=run_ingest,
        start=None,
        end=None,
        symbols=None,
        indexes=None,
        since=None,
        threshold=None,
    )

    args = parser.parse_args(argv)
    args.end = _parse_date(args.end, default=today)
    args.start = _parse_date(args.start, default=args.end)
    if args.symbols:
        args.symbols = [s.strip().upper() for s in args.symbols.split(",")]
    else:
        args.symbols = []
    if args.indexes:
        args.indexes = [s.strip().upper() for s in args.indexes.split(",")]
    else:
        args.indexes = ["VNINDEX"]
    args.since = (
        datetime.fromisoformat(args.since)
        if args.since
        else datetime.combine(args.start, datetime.min.time(), tzinfo=UTC)
    )
    return int(args.func(args))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
