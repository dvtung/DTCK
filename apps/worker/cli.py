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
import json
import logging
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import create_engine

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

    from src.data.providers.base import DataProvider

logger = logging.getLogger("dtck.worker.cli")


def _parse_date(value: str | None, *, default: date) -> date:
    return date.fromisoformat(value) if value else default


def _active_symbols() -> set[str]:
    """Reference symbols used for deterministic news→symbol linking (best effort).

    Without the universe the RSS provider cannot tell a ticker from an arbitrary
    uppercase word, so it would attach no symbol links at all.
    """
    from sqlalchemy import select

    from src.common.models.reference import Stock

    try:
        with _engine().connect() as conn:
            return {
                str(symbol).upper()
                for symbol in conn.scalars(select(Stock.symbol).where(Stock.status == "ACTIVE"))
            }
    except Exception:  # noqa: BLE001 — news still ingests, just without links
        logger.warning("could not load the symbol universe for news matching")
        return set()


def _build_provider(source: str, args: argparse.Namespace) -> DataProvider:
    """Build the provider named by ``source`` ('fixture' = offline rows)."""
    from src.data.providers import create_provider

    if source == "fixture":
        from src.data.providers.fixture import build_fixture_provider

        # ``indexes`` matters for `--dataset index_prices`; without it the fixture
        # provider returns no index bars and the run would report a silent no-op.
        # ``include_financials``/``include_events`` do the same for the GĐ 2
        # datasets (a fixture provider with no financial rows would also no-op).
        return build_fixture_provider(
            symbols=args.symbols or [],
            start=args.start,
            end=args.end,
            indexes=args.indexes or [],
            include_financials=args.dataset == "financials",
            include_events=args.dataset == "events",
        )
    universe = _active_symbols() if args.dataset == "news" else set()
    return create_provider(source, universe=frozenset(universe))


def _engine() -> Engine:
    from apps.api.config import settings

    return create_engine(settings.database_url, pool_pre_ping=True)


def run_ingest(args: argparse.Namespace) -> int:
    """Execute one pipeline run and print its summary + quality gate verdict."""
    from src.data.pipelines import (
        ingest_eod,
        ingest_events,
        ingest_financials,
        ingest_index,
        ingest_macro,
        ingest_news,
    )

    if args.dataset in ("prices", "financials", "events") and not args.symbols:
        # An empty universe would "succeed" while ingesting nothing — fail loudly.
        logger.error("--symbols is required for --dataset %s", args.dataset)
        return 2
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
    elif args.dataset == "financials":
        result = ingest_financials(
            engine,
            provider,
            args.symbols,
            period_types=tuple(args.period_types),
            threshold=args.threshold,
        )
    elif args.dataset == "events":
        result = ingest_events(
            engine, provider, args.symbols, since=args.since.date(), threshold=args.threshold
        )
    elif args.dataset == "macro":
        result = ingest_macro(
            engine,
            provider,
            list(args.indicators or []),
            start=args.start,
            end=args.end,
            threshold=args.threshold,
        )
    else:
        raise ValueError(f"unknown dataset '{args.dataset}'")

    for issue in result.issues:
        logger.warning("validation issue: %s", issue)
    logger.info("%s", result.summary())
    if not result.quality_passed:
        logger.error("quality gate FAILED — dataset flagged below_threshold (§39)")
        return 1
    return 0


def compute_scores(args: argparse.Namespace) -> int:
    """Compute + persist daily factor scores over stored prices (W1b, §12/§43).

    Only price-derived dimensions (technical/momentum/risk) are computed today —
    fundamentals/valuation need provider data that is not available yet
    (KI-006/KI-007), so those dimensions stay NULL instead of being invented.
    """
    from src.quant.factors.scoring import DEFAULT_SCORING_VERSION
    from src.quant.scoring.job import compute_and_store_scores

    result = compute_and_store_scores(
        _engine(),
        lookback=args.lookback,
        scoring_version=args.scoring_version or DEFAULT_SCORING_VERSION,
        as_of=args.as_of,
    )
    logger.info("%s", result.summary())
    if result.scored == 0:
        logger.error("no symbols scored — is `prices` populated for the as-of date?")
        return 1
    return 0


def notify_strategy_changes_command(args: argparse.Namespace) -> int:
    """Email the grade changes between the last two scored sessions (GĐ 6)."""
    from src.quant.strategy.alerts import send_grade_change_alert

    engine = _engine()
    with engine.connect() as conn:
        result = send_grade_change_alert(conn, dry_run=bool(args.dry_run))
    logger.info(
        "strategy alerts: changes=%s sent=%s error=%s",
        result.get("changes"),
        result.get("sent"),
        result.get("error"),
    )
    if args.dry_run and result.get("html"):
        logger.info("preview length=%d chars", len(str(result["html"])))
    return 0 if result.get("success") or result.get("changes") == 0 else 1


def backtest_strategy_command(args: argparse.Namespace) -> int:
    """Backtest the strategy-scoring module (GĐ 5, §16/§43).

    Prints the report (strategy vs VNINDEX buy-and-hold) and exits non-zero only
    when the run produced no equity curve (a configuration/data problem).
    """
    from src.quant.strategy.backtest import run_strategy_backtest

    symbols = [str(s) for s in args.symbols] if args.symbols else list(_active_symbols())
    if not symbols:
        logger.error("--symbols is required (no active universe available)")
        return 2
    report = run_strategy_backtest(
        _engine(),
        symbols,
        args.start,
        args.end,
        profile=args.profile,
        top_n=args.top_n,
        rebalance_days=args.rebalance_days,
    )
    logger.info("%s", report.summary())
    for key in (
        "total_return",
        "cagr",
        "annualized_volatility",
        "sharpe_ratio",
        "sortino_ratio",
        "max_drawdown",
        "calmar_ratio",
        "win_rate",
        "profit_factor",
        "turnover",
        "transaction_cost",
    ):
        value = report.metrics.get(key)
        bench = report.benchmark_metrics.get(key)
        logger.info(
            "  %-24s strategy=%s benchmark=%s",
            key,
            f"{value:.4f}" if value is not None else "n/a",
            f"{bench:.4f}" if bench is not None else "n/a",
        )
    if not report.result.equity_curve:
        logger.error("backtest produced no equity curve")
        return 1
    return 0


def strategy_scores_command(args: argparse.Namespace) -> int:
    """Score the 3 strategy profiles + persist recommendations (GĐ 4, §12/§16)."""
    from src.quant.strategy.job import compute_and_store_strategy_scores

    symbols = [str(s) for s in args.symbols] if args.symbols else None
    as_of = args.as_of or datetime.now(tz=UTC).date()
    result = compute_and_store_strategy_scores(_engine(), as_of, symbols)
    logger.info("%s", result.summary())
    if result.rows_written == 0:
        logger.error("no strategy scores written — run compute-features/prices first?")
        return 1
    return 0


def compute_features_command(args: argparse.Namespace) -> int:
    """Compute + persist strategy features and group scores (GĐ 3, §12/§43)."""
    from src.quant.strategy.feature_engine import compute_and_store_features

    symbols = [str(s) for s in args.symbols] if args.symbols else sorted(_active_symbols())
    if not symbols:
        logger.error("--symbols is required (no active universe available)")
        return 2
    as_of = args.as_of or datetime.now(tz=UTC).date()
    written = compute_and_store_features(_engine(), as_of, symbols)
    logger.info(
        "features version=%s as_of=%s symbols=%d written=%d",
        "strategy_features_v1.0",
        as_of,
        len(symbols),
        written,
    )
    if written == 0:
        logger.error("no features written — are `prices` populated as of %s?", as_of)
        return 1
    return 0


def _train_market_service(source: str) -> Any:
    """Resolve the market source for ``train-model`` (KI-012 unblock).

    ``memory`` is the offline fixture (default — unit tests need no infra);
    ``db`` reads TimescaleDB through ``DbMarketService`` (mixed labels).
    """
    if source == "db":
        from apps.api.services.db_market import DbMarketService

        return DbMarketService()
    from apps.api.services.market_data import MarketService

    return MarketService()


def train_model(args: argparse.Namespace) -> int:
    """Train + calibrate the price-direction model (T014, spec §14.3/§40).

    Builds the feature dataset from the selected source, fits XGBoost with a
    temporal split, calibrates on validation, and registers the model as
    APPROVED in the process registry.  ``--source memory`` (default) uses the
    in-memory fixture, whose monotone prices produce single-class labels the
    trainer rejects honestly (KI-012); ``--source db`` trains on real
    TimescaleDB history, which carries mixed up/down labels.
    """
    from src.ml.feature_dataset import FeatureDatasetBuilder
    from src.ml.model_registry import get_default_registry
    from src.ml.training import ModelTrainer

    symbols = args.symbols or None
    source = getattr(args, "source", "memory") or "memory"
    dataset = FeatureDatasetBuilder(horizon_days=args.horizon).build(
        _train_market_service(source), symbols=symbols
    )
    logger.info(
        "dataset built: %d rows · %d features · source=%s · version %s",
        len(dataset.features),
        dataset.features.shape[1],
        source,
        "feature_v1",
    )
    registry = get_default_registry()
    try:
        entry = ModelTrainer(
            horizon_days=args.horizon, algorithm=getattr(args, "algorithm", "xgboost")
        ).train_and_register(dataset, registry)
    except ValueError as exc:
        logger.error("training rejected: %s", exc)
        return 1

    # Mirror into the model_registry table so the API can hydrate it at startup
    # (T015b) — without this the model dies with this process and /predictions
    # keeps serving the deterministic stub.
    persisted = False
    try:
        from src.ml.registry_store import save_entry

        save_entry(entry, _engine())
        persisted = True
    except Exception as exc:  # noqa: BLE001 — training itself succeeded; report honestly
        logger.warning("model trained but NOT persisted to the registry table: %s", exc)

    logger.info("registered %s v%s (%s)", entry.model_id, entry.version, entry.status)
    print(
        json.dumps(
            {
                "model_id": entry.model_id,
                "version": entry.version,
                "status": entry.status,
                "metrics": entry.metrics,
                "feature_version": entry.feature_version,
                "persisted": persisted,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def run_agent(args: argparse.Namespace) -> int:
    """Run one agent task through the orchestrator and print its audit record.

    Deterministic + offline (no LLM): tools wrap the same in-memory services the
    API uses, so this is a reproducible §31 audit record from the CLI.
    """
    from apps.api.services.agent_service import get_orchestrator
    from src.agents.schemas import PortfolioPosition

    orchestrator = get_orchestrator()
    if args.task in ("analyze", "research") and not args.symbol:
        raise ValueError(f"--symbol is required for --task {args.task}")
    if args.task == "analyze":
        run = orchestrator.analyze(args.symbol)
    elif args.task == "research":
        run = orchestrator.research(args.symbol, query=args.query or "")
    elif args.task == "monitor":
        run = orchestrator.monitor(args.symbols or _default_watchlist())
    else:
        positions = [
            PortfolioPosition(**p) for p in _parse_positions(args.positions or "")
        ]
        run = orchestrator.portfolio(positions)

    logger.info(
        "agent run %s [%s] status=%s latency=%dms tool_calls=%d",
        run.agent_run_id,
        run.agent_id,
        run.status,
        run.latency_ms,
        len(run.tools_called),
    )
    print(json.dumps(run.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0 if run.status == "succeeded" else 1


def _default_watchlist() -> list[str]:
    """Fallback watchlist: every symbol the in-memory market service knows."""
    from apps.api.services.market_data import MarketService

    return [
        str(row["symbol"]) for row in MarketService().list_stocks(None, None, None)
    ]


def _parse_positions(value: str) -> list[dict[str, Any]]:
    """Parse ``FPT:100,VCB:250`` into portfolio position dicts."""
    positions: list[dict[str, Any]] = []
    for chunk in (c.strip() for c in value.split(",")):
        if not chunk:
            continue
        symbol, _, quantity = chunk.partition(":")
        if not symbol or not quantity:
            raise ValueError(f"invalid position '{chunk}' (expected SYMBOL:QUANTITY)")
        positions.append({"symbol": symbol.strip().upper(), "quantity": float(quantity)})
    if not positions:
        raise ValueError("--positions is required for --task portfolio")
    return positions


def build_parser() -> argparse.ArgumentParser:
    """CLI argument parser (shared by ``main`` and tests)."""
    parser = argparse.ArgumentParser(prog="dtck-worker-cli")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="run a data collector pipeline")
    ingest.add_argument(
        "--dataset",
        default="prices",
        choices=["prices", "index_prices", "news", "financials", "events", "macro"],
    )
    ingest.add_argument("--source", default="fixture", help="provider id or 'fixture' (offline)")
    ingest.add_argument("--start", help="window start (YYYY-MM-DD)")
    ingest.add_argument("--end", help="window end (YYYY-MM-DD); default = today")
    ingest.add_argument("--symbols", help="comma-separated tickers for --dataset prices")
    ingest.add_argument("--indexes", help="comma-separated index codes for index_prices")
    ingest.add_argument("--since", help="news: fetch items published after this ISO timestamp")
    ingest.add_argument(
        "--period-types",
        nargs="+",
        default=["QUARTER", "YEAR"],
        help="financials: period types to fetch (default: QUARTER YEAR)",
    )
    ingest.add_argument(
        "--indicators",
        nargs="+",
        default=None,
        help="macro: indicator codes (default: every code configured for the provider)",
    )
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
        period_types=["QUARTER", "YEAR"],
        indicators=None,
    )

    scores = sub.add_parser(
        "compute-scores", help="compute + persist daily factor scores (W1b, §12)"
    )
    scores.add_argument(
        "--lookback", type=int, default=250, help="bars per symbol used for the raw factors"
    )
    scores.add_argument(
        "--scoring-version", default=None, help="scoring version tag (default: baseline_1.0)"
    )
    scores.add_argument(
        "--as-of", default=None, help="YYYY-MM-DD; default = latest trade date in `prices`"
    )
    scores.set_defaults(
        func=compute_scores,
        start=None,
        end=None,
        symbols=None,
        indexes=None,
        since=None,
        threshold=None,
        as_of=None,
    )

    alerts = sub.add_parser(
        "notify-strategy-changes",
        help="email grade changes between the last two scored sessions (GĐ 6)",
    )
    alerts.add_argument(
        "--dry-run", action="store_true", help="build the digest but do not send"
    )
    alerts.set_defaults(
        func=notify_strategy_changes_command,
        symbols=None,
        start=None,
        end=None,
        indexes=None,
        since=None,
        as_of=None,
        dry_run=False,
    )

    backtest = sub.add_parser(
        "backtest-strategy",
        help="backtest the strategy-scoring module vs VNINDEX (GĐ 5, §16)",
    )
    backtest.add_argument("--profile", default="mid", choices=["short", "mid", "long"])
    backtest.add_argument("--top-n", type=int, default=5, help="positions per rebalance")
    backtest.add_argument(
        "--rebalance-days", type=int, default=21, help="trading days between rebalances"
    )
    backtest.add_argument("--start", required=True, help="window start (YYYY-MM-DD)")
    backtest.add_argument("--end", required=True, help="window end (YYYY-MM-DD)")
    backtest.add_argument("--symbols", help="comma-separated tickers (default: all active)")
    backtest.set_defaults(
        func=backtest_strategy_command,
        symbols=None,
        start=None,
        end=None,
        indexes=None,
        since=None,
        as_of=None,
        profile="mid",
        top_n=5,
        rebalance_days=21,
    )

    strategy = sub.add_parser(
        "strategy-scores",
        help="score 3 strategy profiles + recommendations (GĐ 4, §12/§16)",
    )
    strategy.add_argument("--as-of", default=None, help="YYYY-MM-DD; default = today")
    strategy.add_argument("--symbols", help="comma-separated tickers (default: all active)")
    strategy.set_defaults(
        func=strategy_scores_command,
        as_of=None,
        symbols=None,
        start=None,
        end=None,
        indexes=None,
        since=None,
    )

    features = sub.add_parser(
        "compute-features",
        help="compute + persist strategy features & group scores (GĐ 3, §12/§43)",
    )
    features.add_argument("--as-of", default=None, help="YYYY-MM-DD; default = today")
    features.add_argument("--symbols", help="comma-separated tickers (default: active universe)")
    features.set_defaults(
        func=compute_features_command,
        as_of=None,
        symbols=None,
        start=None,
        end=None,
        indexes=None,
        since=None,
    )

    train = sub.add_parser(
        "train-model", help="train + calibrate + register the ML model (T014, §14.3/§40)"
    )
    train.add_argument(
        "--source",
        default="memory",
        choices=["memory", "db"],
        help=(
            "training data source: 'memory' = offline fixture (default, single-class "
            "labels are rejected — KI-012); 'db' = real TimescaleDB history"
        ),
    )
    train.add_argument("--symbols", help="comma-separated tickers (default: full universe)")
    train.add_argument("--horizon", type=int, default=5, help="prediction horizon in trade days")
    train.add_argument(
        "--algorithm",
        default="xgboost",
        choices=["xgboost", "lightgbm"],
        help="gradient-boosting implementation (lightgbm needs the optional [ml] extra)",
    )
    train.set_defaults(
        func=train_model,
        start=None,
        end=None,
        symbols=None,
        indexes=None,
        since=None,
        threshold=None,
    )

    agent = sub.add_parser("run-agent", help="run an AI agent task (§20/§21, offline)")
    agent.add_argument(
        "--task",
        default="analyze",
        choices=["analyze", "research", "monitor", "portfolio"],
    )
    agent.add_argument("--symbol", help="symbol for --task analyze/research")
    agent.add_argument("--query", help="research query for --task research")
    agent.add_argument("--symbols", help="comma-separated watchlist for --task monitor")
    agent.add_argument(
        "--positions", help="positions for --task portfolio, e.g. FPT:100,VCB:250"
    )
    agent.set_defaults(
        func=run_agent,
        start=None,
        end=None,
        symbols=None,
        indexes=None,
        since=None,
        threshold=None,
        query=None,
        positions=None,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: parse args, dispatch, and map result to exit code."""
    args = build_parser().parse_args(argv)
    args.end = _parse_date(args.end, default=datetime.now(tz=UTC).date())
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
    raw_as_of = getattr(args, "as_of", None)
    args.as_of = date.fromisoformat(raw_as_of) if raw_as_of else None
    return int(args.func(args))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
