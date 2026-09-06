"""Worker CLI — one-off operational commands (ingest, backfill, recompute).

Usage:
    python -m apps.worker.cli ingest --source=... --date=YYYY-MM-DD
"""

from __future__ import annotations

import argparse
import logging

logger = logging.getLogger("dtck.worker.cli")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dtck-worker-cli")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="run a data collector")
    ingest.add_argument("--source", required=True, help="collector name, e.g. vndirect, cafef")
    ingest.add_argument("--date", help="date to ingest (YYYY-MM-DD); default = latest")

    args = parser.parse_args(argv)

    if args.command == "ingest":
        # Placeholder until Phase 1 collectors exist (T004).
        logger.info(
            "ingest source=%s date=%s — collector not implemented yet",
            args.source,
            args.date,
        )
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
