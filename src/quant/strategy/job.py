"""Daily strategy-scoring job (GĐ 4): features → 3 profiles → recommendations.

Reads the group scores computed by the feature engine for one ``as_of`` date,
scores every strategy profile (``short``/``mid``/``long``), builds the
A–D recommendation with deterministic price levels, and persists both into
``strategy_scores`` / ``strategy_recommendations``.

Determinism: same ``features`` rows + same ``as_of`` ⇒ same scores (§ADR-001).
No value is invented — groups without a score stay ``NULL`` and the reason is
recorded in ``data_flags``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import Engine, select

from src.quant.strategy.feature_engine import (
    FEATURE_VERSION,
    _active_symbols,
    build_snapshot,
    compute_group_scores,
    compute_snapshots,
)
from src.quant.strategy.features import compute_raw_features
from src.quant.strategy.groups import GROUP_COLUMNS, GROUPS, PROFILES
from src.quant.strategy.recommend import build_recommendation, price_levels, trend_confirmed
from src.quant.strategy.scoring import score_profile

logger = logging.getLogger(__name__)

SCORING_VERSION = "strategy_v1.0"
FEATURE_VERSION_TAG = FEATURE_VERSION

__all__ = ["SCORING_VERSION", "StrategyRunResult", "compute_and_store_strategy_scores"]


@dataclass(slots=True)
class StrategyRunResult:
    """Outcome of one strategy-scoring run (logged by the worker / CLI)."""

    trade_date: date | None = None
    scoring_version: str = SCORING_VERSION
    scored: int = 0
    skipped: int = 0
    rows_written: int = 0
    profiles: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"strategy scores version={self.scoring_version} as_of={self.trade_date} "
            f"scored={self.scored} skipped={self.skipped} written={self.rows_written} "
            f"profiles={','.join(self.profiles) or 'none'}"
        )


def compute_and_store_strategy_scores(
    engine: Engine,
    as_of: date,
    symbols: list[str] | None = None,
) -> StrategyRunResult:
    """Score every strategy profile for ``symbols`` and persist the outcome."""

    from src.common.models.reference import Stock

    active = symbols or _active_symbols(engine)
    result = StrategyRunResult(trade_date=as_of, profiles=list(PROFILES))
    if not active:
        logger.warning("strategy scoring: no active symbols as_of=%s", as_of)
        return result

    snapshots = compute_snapshots(engine, as_of, active)
    if not snapshots.series:
        logger.warning("strategy scoring: no price series for as_of=%s", as_of)
        return result

    raw = {
        symbol: compute_raw_features(build_snapshot(series, as_of))
        for symbol, series in snapshots.series.items()
    }
    group_results = compute_group_scores(raw)

    group_by_symbol: dict[str, dict[str, float | None]] = {
        symbol: {group: None for group in GROUPS} for symbol in raw
    }
    for item in group_results:
        group_by_symbol.setdefault(item.symbol, {})[item.group] = item.score

    closes_by_symbol = {
        symbol: series.closes for symbol, series in snapshots.series.items()
    }
    score_rows, rec_rows, scored, skipped = _score_rows(
        as_of, group_by_symbol, closes_by_symbol
    )
    result.scored = scored
    result.skipped = skipped
    if not score_rows:
        return result

    with engine.connect() as conn:
        id_by_symbol = dict(
            conn.execute(
                select(Stock.symbol, Stock.id).where(
                    Stock.symbol.in_(sorted({r["symbol"] for r in score_rows})),
                    Stock.status == "ACTIVE",
                )
            ).all()
        )

    score_payload = [r for r in score_rows if id_by_symbol.get(str(r["symbol"])) is not None]
    rec_payload = [r for r in rec_rows if id_by_symbol.get(str(r["symbol"])) is not None]

    with engine.begin() as conn:
        for row in score_payload:
            columns = {GROUP_COLUMNS[g]: row["groups"].get(g) for g in GROUPS}
            params = {
                "stock_id": id_by_symbol[str(row["symbol"])],
                "trade_date": row["trade_date"],
                "strategy": row["strategy"],
                **columns,
                "overall_score": row["overall_score"],
                # Confidence lives on strategy_recommendations (1:1 row); the
                # score row carries its inputs under data_flags instead.
                "data_flags": row["data_flags"],
                "scoring_version": SCORING_VERSION,
            }
            conn.execute(*_upsert("strategy_scores", "(stock_id, trade_date, strategy)", params))
        for row in rec_payload:
            levels = row["levels"]
            params = {
                "stock_id": id_by_symbol[str(row["symbol"])],
                "trade_date": row["trade_date"],
                "strategy": row["strategy"],
                "grade": row["grade"],
                "buy_zone_low": levels.buy_zone_low,
                "buy_zone_high": levels.buy_zone_high,
                "stop_loss": levels.stop_loss,
                "target_price": levels.target_price,
                "rr_ratio": levels.rr_ratio,
                "reasons": row["reasons"],
                "risks": row["risks"],
                "confidence": row["confidence"],
                "scoring_version": SCORING_VERSION,
            }
            conn.execute(
                *_upsert(
                    "strategy_recommendations",
                    "(stock_id, trade_date, strategy)",
                    params,
                )
            )

    result.rows_written = len(score_payload)
    return result


#: Columns stored as JSONB — psycopg cannot adapt ``dict``/``list`` directly,
#: so they are serialised to text and cast in the statement.
_JSON_COLUMNS = frozenset({"data_flags", "reasons", "risks"})


def _upsert(table: str, conflict: str, params: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """Build a parameterised upsert + its bind parameters (fixed column set)."""
    from sqlalchemy import text

    keys = list(params)
    values = ", ".join(
        f"cast(:{k} as jsonb)" if k in _JSON_COLUMNS else f":{k}" for k in keys
    )
    updates = ", ".join(
        f"{k} = excluded.{k}" for k in keys if k not in {"stock_id", "trade_date", "strategy"}
    )
    sql = text(
        f"insert into {table} ({', '.join(keys)}) values ({values}) "
        f"on conflict {conflict} do update set {updates}"
    )
    import json

    bind = {
        k: (json.dumps(v, ensure_ascii=False) if k in _JSON_COLUMNS and v is not None else v)
        for k, v in params.items()
    }
    return sql, bind


def _score_rows(
    as_of: date,
    group_by_symbol: dict[str, dict[str, float | None]],
    closes_by_symbol: dict[str, tuple[float, ...]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, int]:
    """Build upsert payloads for ``strategy_scores`` and its recommendations."""
    score_rows: list[dict[str, Any]] = []
    rec_rows: list[dict[str, Any]] = []
    scored = 0
    skipped = 0

    for symbol, groups in group_by_symbol.items():
        closes = closes_by_symbol.get(symbol, ())
        if not closes:
            skipped += 1
            continue
        levels = price_levels(closes)
        uptrend = trend_confirmed(closes)
        for profile in PROFILES:
            result = score_profile(groups, profile)
            if result.overall_score is None:
                skipped += 1
                continue
            scored += 1
            score_rows.append(
                {
                    "symbol": symbol,
                    "trade_date": as_of,
                    "strategy": profile,
                    "groups": groups,
                    "overall_score": round(result.overall_score, 2),
                    "confidence": result.confidence,
                    "data_flags": {
                        "missing_groups": list(result.missing_groups),
                        "n_contributing": len(result.contributions),
                    },
                }
            )
            recommendation = build_recommendation(
                result, trend_confirmed=uptrend if profile == "short" else None
            )
            rec_rows.append(
                {
                    "symbol": symbol,
                    "trade_date": as_of,
                    "strategy": profile,
                    "grade": recommendation.grade,
                    "levels": levels,
                    "reasons": recommendation.reasons,
                    "risks": recommendation.risks,
                    "confidence": recommendation.confidence,
                }
            )
    return score_rows, rec_rows, scored, skipped
