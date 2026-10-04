"""Feature engine (GĐ 3): DB → as-of snapshots → features → group scores.

Reads prices, index prices, financial statements, corporate events and
reference industries, applies the **look-ahead rule** and writes raw + ranked
features into the ``features`` table (one row per feature per stock per day).

Look-ahead rule (§31): a reporting period is visible from
``COALESCE(published_at, report_date + lag)`` where ``lag`` comes from
``configs/strategy_features.yaml`` — the *latest* moment a filing could have
became public, which is the safe direction (never seeing data too early).

Everything is deterministic: same inputs + same ``as_of`` ⇒ same outputs.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import Engine, select

from src.quant.strategy.features import (
    FEATURES,
    FeatureSnapshot,
    PeriodValues,
    compute_raw_features,
    periods_sorted,
)
from src.quant.strategy.groups import GROUPS
from src.quant.strategy.redflags import RedFlagInputs, evaluate_redflags

logger = logging.getLogger(__name__)

FEATURE_VERSION = "strategy_features_v1.0"
DEFAULT_LOOKBACK_DAYS = 300

__all__ = [
    "FEATURE_VERSION",
    "FeatureRow",
    "GroupScoreResult",
    "Snapshots",
    "compute_and_store_features",
    "compute_group_scores",
    "compute_snapshots",
    "load_config",
]


@dataclass(frozen=True)
class FeatureConfig:
    """Validated subset of ``configs/strategy_features.yaml``."""

    version: str
    publication_lag_days: dict[str, int]
    price_lookback_days: int
    quarters_ttm: int
    years_cagr: int


@dataclass(frozen=True)
class RawSeries:
    """As-of slice of one symbol's market + fundamental data."""

    symbol: str
    stock_id: int
    industry: str | None
    closes: tuple[float, ...] = ()
    volumes: tuple[float, ...] = ()
    values: tuple[float, ...] = ()
    index_closes: tuple[float, ...] = ()
    periods: tuple[PeriodValues, ...] = ()
    dividend_amount_ttm: float | None = None
    avg_value_20d: float | None = None
    debt_to_equity: float | None = None
    trading_status: str | None = "NORMAL"


@dataclass(frozen=True)
class Snapshots:
    """Everything the feature step needs, keyed by symbol."""

    as_of: date
    series: dict[str, RawSeries]


@dataclass(frozen=True)
class FeatureRow:
    symbol: str
    feature_name: str
    value: float | None
    group: str


@dataclass(frozen=True)
class GroupScoreResult:
    symbol: str
    group: str
    score: float | None
    n_features: int
    missing: tuple[str, ...]


def _rank_percentile(value: float, distribution: Sequence[float]) -> float:
    """Mid-rank percentile (0-100) — ties share the average of their ranks.

    The project's ``percentile_rank`` uses a strictly-less-than definition,
    which collapses binary/all-equal features to 0 (found live on
    ``catalyst_event_ttm``: every stock with a dividend scored 0). Mid-rank is
    the standard fix: ``(less + 0.5 × equal) / n × 100``.
    """
    if not distribution:
        return 0.0
    less = sum(1 for x in distribution if x < value)
    equal = sum(1 for x in distribution if x == value)
    return (less + 0.5 * equal) / len(distribution) * 100.0


def compute_group_scores(
    raw_by_symbol: dict[str, dict[str, float | None]],
) -> list[GroupScoreResult]:
    """Universe-percentile each feature (direction aware), then average per group.

    A feature that is ``None`` for a symbol is excluded from that symbol's
    group average (the group's coverage shrinks; ``missing`` reports it) — no
    zeros are substituted for absent data.
    """
    spec_by_name = {spec.name: spec for spec in FEATURES}
    distributions: dict[str, list[float]] = {spec.name: [] for spec in FEATURES}
    for values in raw_by_symbol.values():
        for name, value in values.items():
            if value is not None:
                distributions[name].append(value)

    ranked: dict[str, dict[str, float]] = {}
    for symbol, values in raw_by_symbol.items():
        ranked[symbol] = {}
        for name, value in values.items():
            if value is None:
                continue
            spec = spec_by_name.get(name)
            if spec is None:
                continue
            pct = _rank_percentile(value, distributions[name])
            ranked[symbol][name] = pct if spec.direction == 1 else 100.0 - pct

    results: list[GroupScoreResult] = []
    for symbol in sorted(raw_by_symbol):
        for group in GROUPS:
            applicable = [
                spec
                for spec in FEATURES
                if spec.group == group and symbol in raw_by_symbol
            ]
            scored = [
                ranked[symbol][spec.name]
                for spec in applicable
                if ranked.get(symbol, {}).get(spec.name) is not None
            ]
            missing = tuple(
                spec.name
                for spec in applicable
                if ranked.get(symbol, {}).get(spec.name) is None
            )
            results.append(
                GroupScoreResult(
                    symbol=symbol,
                    group=group,
                    score=(sum(scored) / len(scored)) if scored else None,
                    n_features=len(scored),
                    missing=missing,
                )
            )
    return results


def compute_features(
    engine: Engine,
    as_of: date,
    symbols: Sequence[str],
) -> tuple[dict[str, dict[str, float | None]], list[GroupScoreResult]]:
    """Raw features + group scores for ``symbols`` as-of ``as_of``."""
    snapshots = compute_snapshots(engine, as_of, symbols)
    raw = {
        symbol: compute_raw_features(build_snapshot(series, as_of))
        for symbol, series in snapshots.series.items()
    }
    return raw, compute_group_scores(raw)


def compute_and_store_features(
    engine: Engine,
    as_of: date,
    symbols: Sequence[str] | None = None,
) -> int:
    """Persist raw features (``name``) and group scores (``grp:<group>``).

    Rows are upserted on ``features``' primary key, so re-running the same
    day overwrites instead of duplicating. ``symbols=None`` scores the whole
    active universe.
    """
    from sqlalchemy import text

    from src.common.models.reference import Stock

    wanted = list(symbols) if symbols else _active_symbols(engine)
    if not wanted:
        return 0
    raw, group_scores = compute_features(engine, as_of, wanted)
    if not raw:
        return 0

    with engine.connect() as conn:
        id_by_symbol = dict(
            conn.execute(
                select(Stock.symbol, Stock.id).where(
                    Stock.symbol.in_(sorted(raw)), Stock.status == "ACTIVE"
                )
            ).all()
        )

    rows: list[dict[str, Any]] = []
    calculated_at = datetime.now(tz=UTC)
    for symbol, values in raw.items():
        stock_id = id_by_symbol.get(symbol)
        if stock_id is None:
            continue
        for name, value in values.items():
            if value is None:
                continue  # absent data is not persisted as zero
            rows.append(
                {
                    "stock_id": stock_id,
                    "trade_date": as_of,
                    "feature_name": name,
                    "value": value,
                    "feature_version": FEATURE_VERSION,
                    "calculated_at": calculated_at,
                }
            )
    for result in group_scores:
        if result.score is None:
            continue
        stock_id = id_by_symbol.get(result.symbol)
        if stock_id is None:
            continue
        rows.append(
            {
                "stock_id": stock_id,
                "trade_date": as_of,
                "feature_name": f"grp:{result.group}",
                "value": result.score,
                "feature_version": FEATURE_VERSION,
                "calculated_at": calculated_at,
            }
        )
    if not rows:
        return 0

    with engine.begin() as conn:
        for row in rows:
            conn.execute(
                text(
                    "insert into features (stock_id, trade_date, feature_name, value, "
                    "feature_version, calculated_at) values "
                    "(:stock_id, :trade_date, :feature_name, :value, :feature_version, "
                    ":calculated_at) on conflict (stock_id, trade_date, feature_name, "
                    "feature_version) do update set value = excluded.value, "
                    "calculated_at = excluded.calculated_at"
                ),
                row,
            )
    return len(rows)


def _assemble_snapshots(
    wanted: Sequence[str],
    *,
    as_of: date,
    cfg: FeatureConfig,
    stock_rows: Iterable[Any],
    price_rows: Iterable[Any],
    index_rows: Iterable[Any],
    fin_rows: Iterable[Any],
    event_rows: Iterable[Any],
    industry_by_symbol: dict[str, str | None],
    id_by_symbol: dict[str, int],
) -> Snapshots:
    bars_by_symbol: dict[str, list[tuple[float, float, float]]] = {}
    for symbol, close, volume, traded in price_rows:
        bars_by_symbol.setdefault(symbol, []).append(
            (float(close), float(volume or 0), float(traded or 0))
        )
    index_closes = tuple(float(row[0]) for row in index_rows)

    periods_by_symbol: dict[str, dict[tuple[str, int, int], PeriodValues]] = {}
    for symbol, ptype, fy, fp, report_date, published_at, line_item, value in fin_rows:
        published = published_at.date() if published_at else None
        if _usable_from(report_date, published, cfg) > as_of:
            continue  # not yet public as of this date (look-ahead guard)
        key = (str(ptype), int(fy), int(fp))
        holder = periods_by_symbol.setdefault(symbol, {}).setdefault(
            key,
            PeriodValues(
                period_type=str(ptype),
                fiscal_year=int(fy),
                fiscal_period=int(fp),
                report_date=report_date,
                published_at=published,
            ),
        )
        holder.values[str(line_item)] = float(value)

    dividends: dict[str, float] = {}
    window_start = as_of - timedelta(days=365)
    for symbol, event_date, details in event_rows:
        if event_date < window_start or not isinstance(details, dict):
            continue
        amount = details.get("cash_amount")
        if amount is None:
            continue
        dividends[symbol] = dividends.get(symbol, 0.0) + float(amount)

    series: dict[str, RawSeries] = {}
    for symbol in wanted:
        bars = bars_by_symbol.get(symbol, [])
        if not bars:
            continue
        periods = periods_sorted(list(periods_by_symbol.get(symbol, {}).values()))
        equity = _value(periods[-1], "400") if periods else None
        liabilities = _value(periods[-1], "300") if periods else None
        traded = [b[2] for b in bars]
        series[symbol] = RawSeries(
            symbol=symbol,
            stock_id=id_by_symbol.get(symbol, 0),
            industry=industry_by_symbol.get(symbol),
            closes=tuple(b[0] for b in bars),
            volumes=tuple(b[1] for b in bars),
            values=tuple(traded),
            index_closes=index_closes,
            periods=periods,
            dividend_amount_ttm=dividends.get(symbol),
            avg_value_20d=(sum(traded[-20:]) / len(traded[-20:])) if traded else None,
            debt_to_equity=(
                (liabilities / equity) if (liabilities is not None and equity) else None
            ),
        )
    return Snapshots(as_of=as_of, series=series)


def _value(period: PeriodValues | None, code: str) -> float | None:
    return None if period is None else period.values.get(code)


def build_snapshot(series: RawSeries, as_of: date) -> FeatureSnapshot:
    """Wrap a :class:`RawSeries` as the pure feature input + red flags."""
    red_flags = evaluate_redflags(
        RedFlagInputs(
            avg_value_20d_vnd=series.avg_value_20d,
            debt_to_equity=series.debt_to_equity,
            industry=series.industry,
            trading_status=series.trading_status,
            # Not fed by CafeF/Yahoo yet → unchecked, never invented.
            consecutive_loss_years=None,
            operating_cash_flow_negative=None,
            audit_opinion=None,
        )
    )
    return FeatureSnapshot(
        symbol=series.symbol,
        as_of=as_of,
        industry=series.industry,
        closes=series.closes,
        volumes=series.volumes,
        values=series.values,
        index_closes=series.index_closes,
        financials=series.periods,
        dividend_amount_ttm=series.dividend_amount_ttm,
        red_flags=red_flags,
    )


def compute_snapshots(
    engine: Engine,
    as_of: date,
    symbols: Sequence[str],
    *,
    config: FeatureConfig | None = None,
) -> Snapshots:
    """Build as-of snapshots for ``symbols`` (prices, financials, events)."""
    from sqlalchemy import text

    from src.common.models.reference import Stock

    cfg = config or load_config()
    start = as_of - timedelta(days=cfg.price_lookback_days * 2)
    wanted = [s.upper() for s in symbols]

    with engine.connect() as conn:
        stock_rows = conn.execute(
            select(Stock.id, Stock.symbol, Stock.industry_id).where(
                Stock.symbol.in_(wanted), Stock.status == "ACTIVE"
            )
        ).all()
        industry_by_symbol: dict[str, str | None] = {}
        id_by_symbol: dict[str, int] = {}
        for stock_id, symbol, industry_id in stock_rows:
            id_by_symbol[symbol] = stock_id
            if industry_id is None:
                industry_by_symbol[symbol] = None
            else:
                name = conn.execute(
                    text("select name from industries where id = :id"), {"id": industry_id}
                ).scalar_one_or_none()
                industry_by_symbol[symbol] = str(name).lower() if name else None

        # Market series: only bars on or before as_of (never future prints).
        price_rows = conn.execute(
            text(
                "select s.symbol, p.close, p.volume, p.trading_value "
                "from prices p join stocks s on s.id = p.stock_id "
                "where s.symbol = any(:symbols) and p.trade_date <= :as_of "
                "and p.trade_date >= :start order by s.symbol, p.trade_date"
            ),
            {"symbols": wanted, "as_of": as_of, "start": start},
        ).all()
        index_rows = conn.execute(
            text(
                "select close from index_prices where index_code = 'VNINDEX' "
                "and trade_date <= :as_of and trade_date >= :start order by trade_date"
            ),
            {"as_of": as_of, "start": start},
        ).all()
        fin_rows = conn.execute(
            text(
                "select s.symbol, f.period_type, f.fiscal_year, f.fiscal_period, "
                "f.report_date, f.published_at, f.line_item, f.value "
                "from financial_statements f join stocks s on s.id = f.stock_id "
                "where s.symbol = any(:symbols) and f.valid_to is null "
                "order by s.symbol, f.report_date"
            ),
            {"symbols": wanted},
        ).all()
        event_rows = conn.execute(
            text(
                "select s.symbol, e.event_date, e.details from corporate_events e "
                "join stocks s on s.id = e.stock_id "
                "where s.symbol = any(:symbols) and e.event_date <= :as_of"
            ),
            {"symbols": wanted, "as_of": as_of},
        ).all()

    return _assemble_snapshots(
        wanted,
        as_of=as_of,
        cfg=cfg,
        stock_rows=stock_rows,
        price_rows=price_rows,
        index_rows=index_rows,
        fin_rows=fin_rows,
        event_rows=event_rows,
        industry_by_symbol=industry_by_symbol,
        id_by_symbol=id_by_symbol,
    )


def _active_symbols(engine: Engine) -> list[str]:
    """Active universe (sorted) — shared by the feature and scoring jobs."""
    from sqlalchemy import text

    with engine.connect() as conn:
        rows = conn.execute(
            text("select symbol from stocks where status = 'ACTIVE' order by symbol")
        ).all()
    return [str(row[0]) for row in rows]


def load_config(path: str | None = None) -> FeatureConfig:
    """Load + validate ``configs/strategy_features.yaml``."""
    from pathlib import Path

    import yaml  # type: ignore[import-untyped]

    repo_root = Path(__file__).resolve().parents[3]
    target = Path(path) if path else repo_root / "configs" / "strategy_features.yaml"
    with target.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{target}: expected a YAML mapping")
    version = data.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError(f"{target}: missing 'version'")
    lag = data.get("publication_lag_days")
    if not isinstance(lag, dict) or not {"QUARTER", "YEAR"} <= set(lag):
        raise ValueError(f"{target}: publication_lag_days must cover QUARTER and YEAR")
    history = data.get("history") or {}
    return FeatureConfig(
        version=version,
        publication_lag_days={str(k): int(v) for k, v in lag.items()},
        price_lookback_days=int(data.get("price_lookback_days", DEFAULT_LOOKBACK_DAYS)),
        quarters_ttm=int(history.get("quarters_ttm", 4)),
        years_cagr=int(history.get("years_cagr", 4)),
    )


def _usable_from(report_date: date, published_at: date | None, cfg: FeatureConfig) -> date:
    """The earliest date a period may be used (look-ahead rule, §31)."""
    if published_at is not None:
        return published_at
    is_annual = report_date.month == 12 and report_date.day == 31
    key = "YEAR" if is_annual else "QUARTER"
    return report_date + timedelta(days=cfg.publication_lag_days[key])
