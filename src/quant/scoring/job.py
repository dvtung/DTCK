"""Daily scoring job: raw price factors → factor scores → ``factor_scores`` (W1b).

Runs after ingestion (worker CLI ``compute-scores``) and persists what
``/api/v1/stocks/ranked`` reads. The math is delegated to the existing
deterministic modules — this module only *extracts* raw factor values from
stored prices, percentile-ranks them across the universe
(``src/quant/factors/scoring.py``) and upserts the result.

**Honesty note (KI-006/KI-007):** only price-derived dimensions are computed
today — ``technical``, ``momentum`` and ``risk``. The ``fundamental``,
``valuation`` and ``quality`` dimensions need financial statements, which no
provider has supplied yet, so they are stored as ``NULL`` rather than invented.
``compute_overall_score`` renormalizes over the available dimensions, which is
the documented behaviour for missing factors (§12).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import Engine, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.market.momentum import momentum
from src.market.risk import risk
from src.market.technical import indicators as tech
from src.quant.factors.scoring import (
    DEFAULT_SCORING_VERSION,
    WEIGHTS,
    compute_factor_scores,
    compute_overall_score,
)

#: Bars pulled per stock (≈1 trading year) — enough for 63-day momentum + warmup.
DEFAULT_LOOKBACK = 250
#: Periods used by the price-derived raw factors.
RSI_PERIOD = 14
MOMENTUM_PERIOD = 63
VOLATILITY_PERIOD = 20


@dataclass(slots=True)
class ScoreRunResult:
    """Outcome of one scoring run (logged by the worker / CLI)."""

    trade_date: date | None = None
    scoring_version: str = DEFAULT_SCORING_VERSION
    scored: int = 0
    skipped: int = 0
    dimensions: list[str] = field(default_factory=list)

    def summary(self) -> str:
        dims = ",".join(self.dimensions) if self.dimensions else "none"
        return (
            f"scores version={self.scoring_version} trade_date={self.trade_date} "
            f"scored={self.scored} skipped={self.skipped} dimensions={dims}"
        )


def raw_price_factors(closes: list[float]) -> dict[str, float | None]:
    """Raw (unranked) factor values derivable from prices alone.

    * ``technical`` — RSI(14): the momentum oscillator from
      ``docs/QUANT_ENGINE.md`` §2.1.
    * ``momentum`` — 63-day (≈1 quarter) return (§2.4).
    * ``risk`` — **negated** 20-day annualized volatility, so a *higher* raw
      value means *lower* risk (percentile ranking is "higher is better").

    Returns ``None`` per dimension when there is not enough history; callers
    exclude those dimensions instead of substituting a placeholder.
    """
    rsi = tech.rsi(closes, RSI_PERIOD)
    quarter_return = momentum.return_n(closes, MOMENTUM_PERIOD)
    vol = risk.volatility(closes, VOLATILITY_PERIOD)
    return {
        "technical": rsi[-1] if rsi else None,
        "momentum": quarter_return[-1] if quarter_return else None,
        "risk": -vol[-1] if vol and vol[-1] is not None else None,
    }


def load_price_series(
    engine: Engine, *, lookback: int = DEFAULT_LOOKBACK
) -> dict[str, list[tuple[date, float]]]:
    """Latest ``lookback`` closes per ACTIVE stock, oldest first."""
    from src.common.models.market import Price
    from src.common.models.reference import Stock

    stmt = (
        select(Stock.symbol, Price.trade_date, Price.close)
        .join(Stock, Price.stock_id == Stock.id)
        .where(Stock.status == "ACTIVE")
        .order_by(Stock.symbol.asc(), Price.trade_date.asc())
    )
    series: dict[str, list[tuple[date, float]]] = {}
    with engine.connect() as conn:
        for symbol, trade_date, close in conn.execute(stmt):
            series.setdefault(str(symbol), []).append((trade_date, float(close)))
    return {symbol: rows[-lookback:] for symbol, rows in series.items()}


def compute_and_store_scores(
    engine: Engine,
    *,
    lookback: int = DEFAULT_LOOKBACK,
    scoring_version: str = DEFAULT_SCORING_VERSION,
    as_of: date | None = None,
) -> ScoreRunResult:
    """Percentile-rank the price-derived factors for the latest trade date."""
    from src.common.models.quant import FactorScore
    from src.data.normalizers import resolve_stock_ids

    series = load_price_series(engine, lookback=lookback)
    if not series:
        return ScoreRunResult(scoring_version=scoring_version)

    latest = as_of or max(rows[-1][0] for rows in series.values())
    result = ScoreRunResult(trade_date=latest, scoring_version=scoring_version)

    raws: dict[str, dict[str, float | None]] = {}
    for symbol, rows in series.items():
        if rows[-1][0] != latest:
            # Stale symbol (no bar on the as-of date): skip instead of ranking
            # yesterday's data as if it were today's.
            result.skipped += 1
            continue
        raws[symbol] = raw_price_factors([close for _, close in rows])
    if not raws:
        return result

    universe_values: dict[str, list[float]] = {factor: [] for factor in WEIGHTS}
    for raw in raws.values():
        for factor, value in raw.items():
            if value is not None:
                universe_values[factor].append(value)

    scored_rows: list[dict[str, object]] = []
    used_dimensions: set[str] = set()
    with engine.begin() as conn:
        stock_ids = resolve_stock_ids(conn, list(raws))
        for symbol, raw in raws.items():
            stock_id = stock_ids.get(symbol.upper())
            if stock_id is None:
                result.skipped += 1
                continue
            scores = compute_factor_scores(raw, universe_values)
            used_dimensions.update(f for f, v in scores.items() if v is not None)
            scored_rows.append(
                {
                    "stock_id": stock_id,
                    "trade_date": latest,
                    "scoring_version": scoring_version,
                    "technical_score": scores["technical"],
                    "fundamental_score": scores["fundamental"],
                    "valuation_score": scores["valuation"],
                    "momentum_score": scores["momentum"],
                    "quality_score": scores["quality"],
                    "risk_score": scores["risk"],
                    "overall_score": compute_overall_score(scores),
                    "market_regime": None,
                }
            )

        if scored_rows:
            stmt = pg_insert(FactorScore.__table__).values(scored_rows)  # type: ignore[arg-type]
            stmt = stmt.on_conflict_do_update(
                index_elements=["stock_id", "trade_date", "scoring_version"],
                set_={
                    "technical_score": stmt.excluded.technical_score,
                    "fundamental_score": stmt.excluded.fundamental_score,
                    "valuation_score": stmt.excluded.valuation_score,
                    "momentum_score": stmt.excluded.momentum_score,
                    "quality_score": stmt.excluded.quality_score,
                    "risk_score": stmt.excluded.risk_score,
                    "overall_score": stmt.excluded.overall_score,
                },
            )
            conn.execute(stmt)

    result.scored = len(scored_rows)
    result.dimensions = sorted(used_dimensions)
    return result


__all__ = [
    "DEFAULT_LOOKBACK",
    "ScoreRunResult",
    "compute_and_store_scores",
    "load_price_series",
    "raw_price_factors",
]

