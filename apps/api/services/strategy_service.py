"""Read-only access to the strategy-scoring tables (GĐ 6).

Two implementations behind one contract:

* :class:`DbStrategyService` — reads ``strategy_scores``,
  ``strategy_recommendations`` and the ``grp:*`` rows of ``features``.
* :class:`NullStrategyService` — honest empty answers when the database is not
  available (``MARKET_DATA_SOURCE=memory``), so the API keeps working and never
  invents a score.

The endpoints stay read-only: the worker owns every write (§32).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from src.common.models.market import Price
from src.quant.strategy.groups import GROUPS, PROFILES
from src.quant.strategy.job import SCORING_VERSION
from src.quant.strategy.recommend import DISCLAIMER

logger = logging.getLogger(__name__)

__all__ = ["DbStrategyService", "NullStrategyService", "StrategySource"]


class StrategySource:
    """Contract implemented by both strategy readers (duck-typed protocol)."""

    def latest_trade_date(self) -> date | None:  # pragma: no cover - interface
        raise NotImplementedError

    def rankings(
        self, strategy: str, *, universe: str | None = None
    ) -> list[dict[str, Any]]:  # pragma: no cover - interface
        raise NotImplementedError

    def symbol_view(self, symbol: str) -> dict[str, Any] | None:  # pragma: no cover
        raise NotImplementedError

    def history(
        self, symbol: str, strategy: str, *, limit: int = 60
    ) -> list[dict[str, Any]]:  # pragma: no cover - interface
        raise NotImplementedError


class NullStrategyService(StrategySource):
    """No database → honest empty answers (never a fabricated score)."""

    def latest_trade_date(self) -> date | None:
        return None

    def rankings(self, strategy: str, *, universe: str | None = None) -> list[dict[str, Any]]:
        return []

    def symbol_view(self, symbol: str) -> dict[str, Any] | None:
        return None

    def history(self, symbol: str, strategy: str, *, limit: int = 60) -> list[dict[str, Any]]:
        return []


def _num(value: Any) -> float | None:
    return None if value is None else float(value)


_SELECT_RANKING = (
    "select st.id as stock_id, st.symbol, st.company_name, sc.strategy, sc.overall_score, "
    "sc.technical_score, sc.moneyflow_score, sc.growth_score, sc.quality_score, "
    "sc.valuation_score, sc.macro_score, sc.governance_score, sc.data_flags, "
    "rc.grade, rc.buy_zone_low, rc.buy_zone_high, rc.stop_loss, rc.target_price, "
    "rc.rr_ratio, rc.confidence, rc.reasons, rc.risks "
    "from strategy_scores sc "
    "join stocks st on st.id = sc.stock_id "
    "left join strategy_recommendations rc on rc.stock_id = sc.stock_id "
    "and rc.trade_date = sc.trade_date and rc.strategy = sc.strategy "
)


class DbStrategyService(StrategySource):
    """Reads the persisted strategy scores/recommendations from the database."""

    def __init__(self, session_maker: Callable[[], Session] | None = None) -> None:
        if session_maker is None:
            from apps.api.db import session_factory

            session_maker = session_factory
        self._session_maker = session_maker

    def _scope(self) -> Session:
        return self._session_maker()

    # ------------------------------------------------------------------ dates
    def latest_trade_date(self) -> date | None:
        with self._scope() as session:
            return session.execute(
                text("select max(trade_date) from strategy_scores")
            ).scalar_one_or_none()

    # --------------------------------------------------------------- rankings
    def rankings(self, strategy: str, *, universe: str | None = None) -> list[dict[str, Any]]:
        if strategy not in PROFILES:
            raise KeyError(f"unknown strategy {strategy!r} (expected {list(PROFILES)})")
        as_of = self.latest_trade_date()
        if as_of is None:
            return []
        universe_filter = ""
        if universe:
            flag = {"vn30": "is_vn30", "vn100": "is_vn100"}.get(universe.lower())
            if flag is None:
                raise KeyError(f"unknown universe {universe!r} (expected vn30|vn100)")
            universe_filter = f" and st.{flag} = true"
        sql = (
            _SELECT_RANKING
            + "where sc.trade_date = :as_of and sc.strategy = :strategy"
            + universe_filter
            + " order by sc.overall_score desc nulls last, st.symbol"
        )
        with self._scope() as session:
            rows = session.execute(
                text(sql), {"as_of": as_of, "strategy": strategy}
            ).mappings().all()
            if not rows:
                return []

            stock_ids = [int(r["stock_id"]) for r in rows if r.get("stock_id")]
            price_map: dict[int, tuple[float | None, float | None]] = {}
            if stock_ids:
                cutoff = as_of - timedelta(days=14)
                prices_stmt = (
                    select(Price.stock_id, Price.trade_date, Price.close)
                    .where(
                        Price.stock_id.in_(stock_ids),
                        Price.trade_date >= cutoff,
                        Price.trade_date <= as_of,
                    )
                    .order_by(Price.stock_id, Price.trade_date.asc())
                )
                stock_prices: dict[int, list[float]] = {}
                for sid, _dt, close in session.execute(prices_stmt).all():
                    stock_prices.setdefault(int(sid), []).append(float(close))

                for sid, closes in stock_prices.items():
                    if closes:
                        curr = closes[-1]
                        prev = closes[-2] if len(closes) >= 2 else None
                        chg = round(curr - prev, 2) if prev is not None else None
                        price_map[sid] = (curr, chg)

        return [
            self._ranking_row(
                dict(row),
                as_of,
                price=price_map.get(int(row["stock_id"]), (None, None))[0]
                if row.get("stock_id")
                else None,
                change=price_map.get(int(row["stock_id"]), (None, None))[1]
                if row.get("stock_id")
                else None,
            )
            for row in rows
        ]

    @staticmethod
    def _ranking_row(
        row: dict[str, Any],
        as_of: date,
        *,
        price: float | None = None,
        change: float | None = None,
    ) -> dict[str, Any]:
        return {
            "symbol": row["symbol"],
            "company_name": row["company_name"],
            "strategy": row["strategy"],
            "trade_date": as_of,
            "overall_score": _num(row["overall_score"]),
            "grade": row["grade"],
            "group_scores": {group: _num(row[f"{group}_score"]) for group in GROUPS},
            "price": price,
            "current_price": price,
            "change": change,
            "buy_zone_low": _num(row["buy_zone_low"]),
            "buy_zone_high": _num(row["buy_zone_high"]),
            "stop_loss": _num(row["stop_loss"]),
            "target_price": _num(row["target_price"]),
            "rr_ratio": _num(row["rr_ratio"]),
            "confidence": _num(row["confidence"]),
            "reasons": list(row["reasons"] or []),
            "risks": list(row["risks"] or []),
            "data_flags": dict(row["data_flags"] or {}),
            "scoring_version": SCORING_VERSION,
            "disclaimer": DISCLAIMER,
        }

    # ----------------------------------------------------------- symbol view
    def symbol_view(self, symbol: str) -> dict[str, Any] | None:
        as_of = self.latest_trade_date()
        if as_of is None:
            return None
        with self._scope() as session:
            stock = session.execute(
                text("select id, symbol, company_name from stocks where symbol = :s"),
                {"s": symbol.upper()},
            ).mappings().first()
            if stock is None:
                return None
            profiles = session.execute(
                text(
                    _SELECT_RANKING
                    + "where sc.stock_id = :id and sc.trade_date = :as_of "
                    + "order by sc.strategy"
                ),
                {"id": stock["id"], "as_of": as_of},
            ).mappings().all()

            price_val: float | None = None
            chg_val: float | None = None
            if stock["id"] is not None:
                cutoff = as_of - timedelta(days=14)
                p_stmt = (
                    select(Price.close)
                    .where(
                        Price.stock_id == stock["id"],
                        Price.trade_date >= cutoff,
                        Price.trade_date <= as_of,
                    )
                    .order_by(Price.trade_date.asc())
                )
                closes = [float(c) for c in session.scalars(p_stmt).all()]
                if closes:
                    price_val = closes[-1]
                    prev = closes[-2] if len(closes) >= 2 else None
                    chg_val = round(price_val - prev, 2) if prev is not None else None

        return {
            "symbol": stock["symbol"],
            "company_name": stock["company_name"],
            "trade_date": as_of,
            "price": price_val,
            "change": chg_val,
            "profiles": [
                self._ranking_row(dict(row), as_of, price=price_val, change=chg_val)
                for row in profiles
            ],
        }

    # ---------------------------------------------------------------- history
    def history(self, symbol: str, strategy: str, *, limit: int = 60) -> list[dict[str, Any]]:
        if strategy not in PROFILES:
            raise KeyError(f"unknown strategy {strategy!r} (expected {list(PROFILES)})")
        with self._scope() as session:
            rows = session.execute(
                text(
                    "select sc.trade_date, sc.overall_score, rc.grade "
                    "from strategy_scores sc join stocks st on st.id = sc.stock_id "
                    "left join strategy_recommendations rc on rc.stock_id = sc.stock_id "
                    "and rc.trade_date = sc.trade_date and rc.strategy = sc.strategy "
                    "where st.symbol = :s and sc.strategy = :strategy "
                    "order by sc.trade_date desc limit :limit"
                ),
                {"s": symbol.upper(), "strategy": strategy, "limit": limit},
            ).mappings().all()
        return [
            {
                "trade_date": row["trade_date"],
                "overall_score": _num(row["overall_score"]),
                "grade": row["grade"],
            }
            for row in reversed(rows)
        ]
