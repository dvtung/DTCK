"""Backtest the strategy-scoring module (GĐ 5).

Answers "does this ranking actually make money?" with the project's existing
engine (``src/backtesting``): every rebalance date gets scores computed **as-of
that date only** (financials filtered by ``published_at``/lag — see
``feature_engine``), the engine then fills at the **next day's open**, and
costs/slippage come from ``ExecutionCosts``.

Conventions documented here (not hidden):
* **Carry-forward for halted days** — the master calendar comes from the
  benchmark/index; a symbol that did not trade on a date keeps its previous
  bar (``volume=0``). This is a backtest convention for missing prints, not a
  new observation; nothing is written back to ``prices``.
* The benchmark (VNINDEX) is reported as a buy-and-hold curve over the same
  window so the report can compare strategy vs index (§16 report).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import Engine, text

from src.backtesting.engine import Strategy, run_backtest
from src.backtesting.metrics import compute_metrics
from src.backtesting.models import (
    BacktestConfig,
    BacktestData,
    BacktestResult,
    EquityPoint,
    ExecutionCosts,
    PriceBar,
)
from src.quant.strategy.feature_engine import (
    build_snapshot,
    compute_group_scores,
    compute_snapshots,
)
from src.quant.strategy.features import compute_raw_features
from src.quant.strategy.groups import PROFILES
from src.quant.strategy.scoring import score_profile

logger = logging.getLogger(__name__)

DEFAULT_BENCHMARK = "VNINDEX"
DEFAULT_TOP_N = 5
DEFAULT_REBALANCE_DAYS = 21

__all__ = [
    "BacktestReport",
    "DEFAULT_TOP_N",
    "build_strategy",
    "load_backtest_data",
    "rebalance_dates",
    "run_strategy_backtest",
    "score_schedule",
    "top_weights",
]


def load_backtest_data(
    engine: Engine,
    symbols: Sequence[str],
    start: date,
    end: date,
    *,
    benchmark: str = DEFAULT_BENCHMARK,
    lookback_days: int = 300,
) -> BacktestData:
    """Aligned OHLCV for ``symbols`` plus the benchmark, in ``[start, end]``.

    Bars are read from ``prices``/``index_prices`` only — never synthesised.
    Missing dates are forward-filled from the last observed bar (``volume=0``),
    which is the documented halt-day convention; a symbol that never traded in
    the window is dropped rather than fabricated.
    """
    wanted = [s.upper() for s in symbols]
    window_start = start - timedelta(days=lookback_days)

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "select s.symbol as symbol, p.trade_date as trade_date, p.open as open, "
                "p.high as high, p.low as low, p.close as close, p.volume as volume "
                "from prices p join stocks s on s.id = p.stock_id "
                "where s.symbol = any(:symbols) and p.trade_date <= :end "
                "and p.trade_date >= :start order by p.trade_date"
            ),
            {"symbols": wanted, "start": window_start, "end": end},
        ).mappings().all()
        bench_rows = conn.execute(
            text(
                "select trade_date as trade_date, open as open, high as high, low as low, "
                "close as close, volume as volume from index_prices "
                "where index_code = :code and trade_date <= :end and trade_date >= :start "
                "order by trade_date"
            ),
            {"code": benchmark, "start": window_start, "end": end},
        ).mappings().all()

    by_symbol: dict[str, dict[date, PriceBar]] = {}
    for row in rows:
        symbol = str(row["symbol"])
        trade_date = row["trade_date"]
        by_symbol.setdefault(symbol, {})[trade_date] = PriceBar(
            date=trade_date,
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"] or 0),
        )

    bench_by_date = {
        row["trade_date"]: PriceBar(
            date=row["trade_date"],
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"] or 0),
        )
        for row in bench_rows
    }

    # Master calendar: prefer the benchmark's trading days (the comparison is
    # only meaningful on the same days); fall back to the union of symbols.
    calendar = sorted(d for d in bench_by_date if start <= d <= end)
    if not calendar:
        calendar = sorted(
            {d for bars in by_symbol.values() for d in bars if start <= d <= end}
        )
    if not calendar:
        raise ValueError(f"no bars for {wanted} in [{start}, {end}]")

    bars: dict[str, list[PriceBar]] = {}
    for symbol, symbol_bars in by_symbol.items():
        first_day = min(symbol_bars) if symbol_bars else None
        if first_day is None or first_day > calendar[0]:
            # No print on/before the first calendar day: leading padding would
            # require future prices (look-ahead) — drop the symbol instead.
            logger.warning(
                "dropping %s from the backtest universe: first print %s is after %s",
                symbol,
                first_day,
                calendar[0],
            )
            continue
        aligned: list[PriceBar] = []
        previous: PriceBar | None = None
        for day in calendar:
            bar = symbol_bars.get(day)
            if bar is not None:
                aligned.append(bar)
                previous = bar
            elif previous is not None:
                # Halt day: carry the last observed bar forward with volume=0.
                aligned.append(
                    PriceBar(
                        date=day,
                        open=previous.open,
                        high=previous.high,
                        low=previous.low,
                        close=previous.close,
                        volume=0.0,
                    )
                )
        if len(aligned) == len(calendar):
            bars[symbol] = aligned

    benchmark_bars = [bench_by_date.get(d, _empty_bar(d)) for d in calendar]
    return BacktestData(dates=calendar, symbols=sorted(bars), bars=bars, benchmark=benchmark_bars)


def _empty_bar(day: date) -> PriceBar:
    """Placeholder benchmark bar (missing index day) — flat, never directional."""
    return PriceBar(date=day, open=0.0, high=0.0, low=0.0, close=0.0, volume=0.0)


def rebalance_dates(dates: Sequence[date], *, every_days: int) -> list[date]:
    """Rebalance calendar: first date, then every ``every_days`` trading days."""
    if every_days < 1:
        raise ValueError("every_days must be >= 1")
    if not dates:
        return []
    return [dates[i] for i in range(0, len(dates), every_days)]


@dataclass(frozen=True)
class BacktestReport:
    """Strategy backtest outcome vs the benchmark (§16)."""

    profile: str
    start: date
    end: date
    top_n: int
    rebalance_days: int
    result: BacktestResult
    benchmark_metrics: dict[str, float] = field(default_factory=dict)
    schedule_size: int = 0

    @property
    def metrics(self) -> dict[str, float]:
        return self.result.metrics

    def summary(self) -> str:
        m = self.result.metrics
        b = self.benchmark_metrics
        return (
            f"backtest profile={self.profile} {self.start}→{self.end} "
            f"top_n={self.top_n} every={self.rebalance_days}d "
            f"total_return={m.get('total_return', 0):.2%} "
            f"sharpe={m.get('sharpe_ratio', 0):.2f} "
            f"max_dd={m.get('max_drawdown', 0):.2%} "
            f"win_rate={m.get('win_rate', 0):.2%} "
            f"| benchmark total_return={b.get('total_return', 0):.2%} "
            f"max_dd={b.get('max_drawdown', 0):.2%}"
        )


def score_schedule(
    engine: Engine,
    symbols: Sequence[str],
    as_of_dates: Sequence[date],
    *,
    profile: str,
) -> dict[date, dict[str, float]]:
    """Profile score per symbol for each rebalance date — **as-of only**.

    Every date re-runs the feature engine with that date as ``as_of``, so
    financials are filtered by the look-ahead rule and only bars on or before
    the date are seen. The engine then trades at the *next* day's open.
    """
    if profile not in PROFILES:
        raise KeyError(f"unknown profile {profile!r} (expected one of {list(PROFILES)})")

    schedule: dict[date, dict[str, float]] = {}
    for as_of in as_of_dates:
        snapshots = compute_snapshots(engine, as_of, symbols)
        if not snapshots.series:
            logger.warning("no price series as_of=%s — skipping rebalance", as_of)
            continue
        raw = {
            symbol: compute_raw_features(build_snapshot(series, as_of))
            for symbol, series in snapshots.series.items()
        }
        per_symbol: dict[str, dict[str, float | None]] = {}
        for item in compute_group_scores(raw):
            per_symbol.setdefault(item.symbol, {})[item.group] = item.score

        scores: dict[str, float] = {}
        for symbol, groups in per_symbol.items():
            overall = score_profile(groups, profile).overall_score
            if overall is not None:
                scores[symbol] = overall
        if scores:
            schedule[as_of] = scores
        else:
            logger.warning("no scores as_of=%s — skipping rebalance", as_of)
    return schedule


def top_weights(scores: dict[str, float], top_n: int) -> dict[str, float]:
    """Equal weights over the ``top_n`` highest scores (ties broken by symbol)."""
    if top_n < 1:
        raise ValueError("top_n must be >= 1")
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:top_n]
    if not ranked:
        return {}
    weight = 1.0 / len(ranked)
    return {symbol: weight for symbol, _ in ranked}


def build_strategy(
    schedule: dict[date, dict[str, float]],
    *,
    top_n: int,
    universe: set[str],
) -> Strategy:
    """Turn a score schedule into the engine's ``Strategy`` callable.

    Returns the top-N equal weights on a rebalance date and ``{}`` otherwise —
    the engine keeps the previous positions on ``{}`` (no forced trading), and
    fills happen at the next open (no look-ahead).
    """

    def _strategy(data: BacktestData, i: int, ctx: dict[str, object]) -> dict[str, float]:
        day = data.dates[i]
        scores = schedule.get(day)
        if not scores:
            return {}
        visible = {s: v for s, v in scores.items() if s in universe}
        weights = top_weights(visible, top_n)
        ctx["last_rebalance"] = day.isoformat()
        return weights

    return _strategy


def _benchmark_metrics(bars: list[PriceBar], initial_capital: float) -> dict[str, float]:
    """Buy-and-hold metrics for the benchmark over the same window."""
    valid = [b for b in bars if b.close > 0]
    if len(valid) < 2:
        return {}
    base = valid[0].close
    curve = [
        EquityPoint(date=b.date, equity=initial_capital * (b.close / base)) for b in valid
    ]
    return compute_metrics(curve, [], initial_capital=initial_capital)


def run_strategy_backtest(
    engine: Engine,
    symbols: Sequence[str],
    start: date,
    end: date,
    *,
    profile: str = "mid",
    top_n: int = DEFAULT_TOP_N,
    rebalance_days: int = DEFAULT_REBALANCE_DAYS,
    benchmark: str = DEFAULT_BENCHMARK,
    costs: ExecutionCosts | None = None,
    initial_capital: float = 1_000_000_000.0,
) -> BacktestReport:
    """Run the strategy-scoring backtest and compare it with the benchmark."""
    if profile not in PROFILES:
        raise KeyError(f"unknown profile {profile!r} (expected one of {list(PROFILES)})")

    data = load_backtest_data(engine, symbols, start, end, benchmark=benchmark)
    window_dates = [d for d in data.dates if start <= d <= end]
    rebalance = rebalance_dates(window_dates, every_days=rebalance_days)
    schedule = score_schedule(engine, data.symbols, rebalance, profile=profile)

    strategy = build_strategy(schedule, top_n=top_n, universe=set(data.symbols))
    config = BacktestConfig(
        strategy_name=f"strategy_scoring_{profile}",
        strategy_version="strategy_v1.0",
        universe=list(data.symbols),
        start_date=start,
        end_date=end,
        params={
            "profile": profile,
            "top_n": top_n,
            "rebalance_days": rebalance_days,
            "benchmark": benchmark,
        },
        costs=costs or ExecutionCosts(),
        run_type="single",
    )
    result = run_backtest(data, strategy, config)
    return BacktestReport(
        profile=profile,
        start=start,
        end=end,
        top_n=top_n,
        rebalance_days=rebalance_days,
        result=result,
        benchmark_metrics=_benchmark_metrics(data.benchmark, initial_capital),
        schedule_size=len(schedule),
    )
