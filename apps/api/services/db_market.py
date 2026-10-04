"""TimescaleDB-backed market-data source for the API read path (W1, KI-008).

Reads exactly what the ingestion pipeline wrote (``src/data/pipelines.py``) plus
what the quant/backtest jobs persist — no synthetic fallbacks. When a dataset is
empty the source returns honest empty/``None`` payloads so routers answer 404 or
an empty page instead of fabricated numbers.

Derived values (technical indicators, rankings, breadth) are **computed on read**
by the same deterministic modules the in-memory source and the worker use
(``src/market/technical/indicators.py``, ``src/quant/scoring/engine.py``), so the
two sources cannot drift apart.

Threading: the instance is shared process-wide (like the in-memory source), so
each public call opens and closes its own short-lived read session instead of
holding one for the object's lifetime.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from apps.api.services.ranking_payload import to_ranking_payload
from src.common.models.backtest import Backtest, BacktestMetric, BacktestTrade
from src.common.models.events import News, NewsSymbol
from src.common.models.fundamental import FinancialRatio, FinancialStatement
from src.common.models.governance import DataQualityScore
from src.common.models.market import IndexPrice, Price, ValuationDaily
from src.common.models.quant import FactorScore, Feature, MarketRegime
from src.common.models.reference import Exchange, Industry, Sector, Stock
from src.market.technical import indicators as tech
from src.quant.scoring.engine import score_universe

#: How many rows the read path returns for unbounded collections.
DEFAULT_LIMIT = 200
#: Valuation/statement history depth served to the dashboard.
HISTORY_LIMIT = 60
#: Factor keys persisted in ``factor_scores`` (mirrors ``src.quant.factors.scoring.WEIGHTS``).
FACTOR_COLUMNS = ("technical", "fundamental", "valuation", "momentum", "quality", "risk")
#: Quarter-end (month, day) lookup for fiscal periods; 0 = full year.
_QUARTER_END = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}


def _f(value: Decimal | float | int | None) -> float | None:
    """Decimal/None → float/None (JSON-friendly)."""
    return None if value is None else float(value)


def _price_row(row: Price) -> dict[str, Any]:
    return {
        "trade_date": row.trade_date,
        "open": float(row.open),
        "high": float(row.high),
        "low": float(row.low),
        "close": float(row.close),
        "volume": int(row.volume),
    }


def _index_row(row: IndexPrice) -> dict[str, Any]:
    return {
        "index_code": row.index_code,
        "trade_date": row.trade_date,
        "open": float(row.open),
        "high": float(row.high),
        "low": float(row.low),
        "close": float(row.close),
        "volume": int(row.volume),
    }


def _period_end(period_type: str, fiscal_year: int, fiscal_period: int) -> date:
    """Map a fiscal period to its period-end date (fiscal_period 0 = full year)."""
    if period_type.upper() == "YEAR" or fiscal_period == 0:
        return date(fiscal_year, 12, 31)
    month, day = _QUARTER_END.get(fiscal_period, (12, 31))
    return date(fiscal_year, month, day)


class DbMarketService:
    """Read-only ``MarketSource`` over PostgreSQL/TimescaleDB (one session per call)."""

    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        if session_factory is None:
            from apps.api.db import session_factory as default_session_factory

            session_factory = default_session_factory
        self._session_factory = session_factory

    @contextmanager
    def _scope(self) -> Iterator[Session]:
        """Short-lived read session: shared instances stay thread-safe."""
        session = self._session_factory()
        try:
            yield session
        finally:
            session.close()

    # ------------------------------------------------------------- internals
    @staticmethod
    def _stock_id(session: Session, symbol: str) -> int | None:
        return session.scalar(select(Stock.id).where(func.upper(Stock.symbol) == symbol.upper()))

    @staticmethod
    def _latest_trade_date(session: Session) -> date | None:
        return session.scalar(select(func.max(Price.trade_date)))

    @staticmethod
    def _latest_closes(session: Session) -> dict[int, float]:
        """Latest close per stock_id (DISTINCT ON stock_id, newest date first)."""
        stmt = (
            select(Price.stock_id, Price.close)
            .distinct(Price.stock_id)
            .order_by(Price.stock_id, Price.trade_date.desc())
        )
        return {stock_id: float(close) for stock_id, close in session.execute(stmt)}

    @staticmethod
    def _reference_statement() -> Any:
        return (
            select(Stock, Exchange.code, Sector.code, Industry.code)
            .join(Exchange, Stock.exchange_id == Exchange.id)
            .outerjoin(Sector, Stock.sector_id == Sector.id)
            .outerjoin(Industry, Stock.industry_id == Industry.id)
        )

    @classmethod
    def _reference_rows(cls, session: Session, statement: Any) -> list[dict[str, Any]]:
        """Reference rows + exchange/sector/industry codes + latest close."""
        closes = cls._latest_closes(session)
        rows: list[dict[str, Any]] = []
        for row in session.execute(statement):
            stock = cast(Stock, row[0])
            exchange_code, sector_code, industry_code = row[1], row[2], row[3]
            rows.append(
                {
                    "symbol": stock.symbol,
                    "company_name": stock.company_name,
                    "exchange": exchange_code,
                    "sector": sector_code,
                    "industry": industry_code,
                    "listed_date": stock.listed_date,
                    "status": stock.status,
                    "is_vn30": bool(stock.is_vn30),
                    "is_vn100": bool(stock.is_vn100),
                    "price": closes.get(stock.id),
                }
            )
        return rows

    # ---------------------------------------------------------------- market
    def list_indices(self) -> list[dict[str, Any]]:
        sql = text("""
            with ranked as (
                select index_code, trade_date, open, high, low, close, volume,
                       lag(close) over (
                           partition by index_code order by trade_date asc
                       ) as prev_close,
                       row_number() over (
                           partition by index_code order by trade_date desc
                       ) as rn
                from index_prices
            )
            select index_code, trade_date, open, high, low, close, volume,
                   (close - prev_close) as change,
                   case when prev_close is not null and prev_close > 0
                        then (close - prev_close) / prev_close
                        else null end as change_pct
            from ranked
            where rn = 1
            order by index_code;
        """)
        with self._scope() as session:
            rows = session.execute(sql).all()
            return [
                {
                    "index_code": str(r.index_code),
                    "trade_date": r.trade_date,
                    "open": float(r.open),
                    "high": float(r.high),
                    "low": float(r.low),
                    "close": float(r.close),
                    "volume": int(r.volume),
                    "change": round(float(r.change), 2) if r.change is not None else None,
                    "change_pct": (
                        round(float(r.change_pct), 6) if r.change_pct is not None else None
                    ),
                }
                for r in rows
            ]

    def get_index(self, code: str) -> dict[str, Any] | None:
        sql = text("""
            with ranked as (
                select index_code, trade_date, open, high, low, close, volume,
                       lag(close) over (
                           partition by index_code order by trade_date asc
                       ) as prev_close,
                       row_number() over (
                           partition by index_code order by trade_date desc
                       ) as rn
                from index_prices
                where upper(index_code) = upper(:code)
            )
            select index_code, trade_date, open, high, low, close, volume,
                   (close - prev_close) as change,
                   case when prev_close is not null and prev_close > 0
                        then (close - prev_close) / prev_close
                        else null end as change_pct
            from ranked
            where rn = 1;
        """)
        with self._scope() as session:
            r = session.execute(sql, {"code": code}).first()
            if not r:
                return None
            return {
                "index_code": str(r.index_code),
                "trade_date": r.trade_date,
                "open": float(r.open),
                "high": float(r.high),
                "low": float(r.low),
                "close": float(r.close),
                "volume": int(r.volume),
                "change": round(float(r.change), 2) if r.change is not None else None,
                "change_pct": (
                    round(float(r.change_pct), 6) if r.change_pct is not None else None
                ),
            }

    def get_index_prices(self, code: str) -> list[dict[str, Any]] | None:
        stmt = (
            select(IndexPrice)
            .where(func.upper(IndexPrice.index_code) == code.upper())
            .order_by(IndexPrice.trade_date.asc())
        )
        with self._scope() as session:
            rows = [_index_row(row) for row in session.scalars(stmt)]
        return rows or None

    def get_regime(self) -> dict[str, Any]:
        stmt = select(MarketRegime).order_by(MarketRegime.trade_date.desc()).limit(1)
        with self._scope() as session:
            row = session.scalars(stmt).first()
            if row is None:
                # Nothing detected yet: report UNKNOWN rather than inventing BULL/BEAR.
                return {
                    "regime": "UNKNOWN",
                    "confidence": 0.0,
                    "trade_date": self._latest_trade_date(session) or date.today(),
                }
            return {
                "regime": row.regime,
                "confidence": _f(row.confidence) or 0.0,
                "trade_date": row.trade_date,
            }

    def get_breadth(self) -> dict[str, Any]:
        """Advancers/decliners/unchanged + participation from the price history."""
        with self._scope() as session:
            dates = list(
                session.scalars(
                    select(Price.trade_date).distinct().order_by(Price.trade_date.desc()).limit(2)
                )
            )
            if not dates:
                return {
                    "trade_date": date.today(),
                    "advancers": 0,
                    "decliners": 0,
                    "unchanged": 0,
                    "participation": None,
                }

            current = dates[0]
            rows: dict[int, Decimal] = {
                stock_id: close
                for stock_id, close in session.execute(
                    select(Price.stock_id, Price.close).where(Price.trade_date == current)
                )
            }
            universe = session.scalar(
                select(func.count()).select_from(Stock).where(Stock.status == "ACTIVE")
            )
            participation = round(len(rows) / universe, 4) if universe else None
            if len(dates) < 2:
                return {
                    "trade_date": current,
                    "advancers": 0,
                    "decliners": 0,
                    "unchanged": 0,
                    "participation": participation,
                }

            previous: dict[int, Decimal] = {
                stock_id: close
                for stock_id, close in session.execute(
                    select(Price.stock_id, Price.close).where(Price.trade_date == dates[1])
                )
            }
            advancers = decliners = unchanged = 0
            for stock_id, close in rows.items():
                before = previous.get(stock_id)
                if before is None:
                    continue
                if close > before:
                    advancers += 1
                elif close < before:
                    decliners += 1
                else:
                    unchanged += 1
            return {
                "trade_date": current,
                "advancers": advancers,
                "decliners": decliners,
                "unchanged": unchanged,
                "participation": participation,
            }

    def get_movers(
        self,
        universe: str = "VN100",
        limit: int = 10,
    ) -> dict[str, Any]:
        """Top gainers and decliners with MA20 / MA50 deviation metrics."""
        with self._scope() as session:
            dates = list(
                session.scalars(
                    select(Price.trade_date).distinct().order_by(Price.trade_date.desc()).limit(2)
                )
            )
            if not dates:
                return {"trade_date": date.today(), "gainers": [], "decliners": []}
            current_date = dates[0]

            # Build query for target universe stocks
            stock_stmt = select(Stock.id, Stock.symbol, Stock.company_name, Exchange.code).join(
                Exchange, Stock.exchange_id == Exchange.id
            ).where(Stock.status == "ACTIVE")

            u_clean = universe.upper().strip()
            if u_clean not in ("VN30", "VN100", "HNX", "HNX30", "UPCOM", "HOSE", "ALL"):
                return {"trade_date": current_date, "gainers": [], "decliners": []}
            if u_clean == "VN30":
                stock_stmt = stock_stmt.where(Stock.is_vn30.is_(True))
            elif u_clean == "VN100":
                stock_stmt = stock_stmt.where(Stock.is_vn100.is_(True))
            elif u_clean in ("HNX", "HNX30"):
                stock_stmt = stock_stmt.where(Exchange.code == "HNX")
            elif u_clean == "UPCOM":
                stock_stmt = stock_stmt.where(Exchange.code == "UPCOM")
            elif u_clean == "HOSE":
                stock_stmt = stock_stmt.where(Exchange.code == "HOSE")

            target_stocks = session.execute(stock_stmt).all()
            if not target_stocks:
                return {"trade_date": current_date, "gainers": [], "decliners": []}

            stock_ids = [row[0] for row in target_stocks]
            stock_meta = {
                row[0]: {"symbol": row[1], "company_name": row[2], "exchange": row[3]}
                for row in target_stocks
            }

            # Fetch recent price bars only: ~100 calendar days ≈ 65 trading
            # sessions covers MA50 + a 1-day change baseline.
            cutoff = current_date - timedelta(days=100)
            prices_stmt = (
                select(Price.stock_id, Price.trade_date, Price.close)
                .where(Price.stock_id.in_(stock_ids), Price.trade_date >= cutoff)
                .order_by(Price.stock_id, Price.trade_date.asc())
            )
            # Group closes by stock_id
            stock_prices: dict[int, list[float]] = {}
            for sid, _dt, close in session.execute(prices_stmt).all():
                stock_prices.setdefault(sid, []).append(float(close))

            items: list[dict[str, Any]] = []
            for sid, meta in stock_meta.items():
                closes = stock_prices.get(sid) or []
                if len(closes) < 2:
                    continue
                curr = closes[-1]
                prev = closes[-2]
                chg = round((curr / prev - 1.0) * 100, 2) if prev else 0.0

                sma20 = round(sum(closes[-20:]) / 20, 2) if len(closes) >= 20 else None
                sma50 = round(sum(closes[-50:]) / 50, 2) if len(closes) >= 50 else None
                p_vs_sma20 = round((curr / sma20 - 1.0) * 100, 2) if sma20 else None
                p_vs_sma50 = round((curr / sma50 - 1.0) * 100, 2) if sma50 else None

                items.append({
                    "symbol": meta["symbol"],
                    "company_name": meta["company_name"],
                    "exchange": meta["exchange"],
                    "close": curr,
                    "change_pct": chg,
                    "sma20": sma20,
                    "price_vs_sma20": p_vs_sma20,
                    "sma50": sma50,
                    "price_vs_sma50": p_vs_sma50,
                })

            gainers = sorted(items, key=lambda x: x["change_pct"], reverse=True)[:limit]
            decliners = sorted(items, key=lambda x: x["change_pct"])[:limit]
            return {
                "trade_date": current_date,
                "gainers": gainers,
                "decliners": decliners,
            }

    # ---------------------------------------------------------------- stocks
    def list_stocks(
        self,
        exchange: str | None,
        sector: str | None,
        vn30: bool | None,
        vn100: bool | None = None,
    ) -> list[dict[str, Any]]:
        stmt = self._reference_statement().where(Stock.status == "ACTIVE")
        if exchange:
            stmt = stmt.where(func.upper(Exchange.code) == exchange.upper())
        if sector:
            stmt = stmt.where(func.upper(Sector.code) == sector.upper())
        if vn30:
            stmt = stmt.where(Stock.is_vn30.is_(True))
        if vn100:
            stmt = stmt.where(Stock.is_vn100.is_(True))
        with self._scope() as session:
            rows = self._reference_rows(session, stmt)
        return sorted(rows, key=lambda row: str(row["symbol"]))

    def get_stock(self, symbol: str) -> dict[str, Any] | None:
        # Delisted instruments still resolve here (anti-survivorship-bias §17);
        # only ``list_stocks`` limits the universe to ACTIVE rows.
        stmt = self._reference_statement().where(func.upper(Stock.symbol) == symbol.upper())
        with self._scope() as session:
            rows = self._reference_rows(session, stmt)
        return rows[0] if rows else None

    def get_prices(self, symbol: str) -> list[dict[str, Any]] | None:
        with self._scope() as session:
            stock_id = self._stock_id(session, symbol)
            if stock_id is None:
                return None
            stmt = select(Price).where(Price.stock_id == stock_id).order_by(Price.trade_date.asc())
            rows = [_price_row(row) for row in session.scalars(stmt)]
        return rows or None

    # --------------------------------------------------------------- ranking
    def get_ranked(self) -> list[dict[str, Any]]:
        """Rank from the latest persisted ``factor_scores`` run (empty when none)."""
        from apps.api.config import settings

        with self._scope() as session:
            latest = session.scalar(
                select(func.max(FactorScore.trade_date)).where(
                    FactorScore.scoring_version == settings.scoring_version
                )
            )
            if latest is None:
                return []

            stmt = (
                select(Stock.symbol, FactorScore)
                .join(Stock, FactorScore.stock_id == Stock.id)
                .where(
                    FactorScore.trade_date == latest,
                    FactorScore.scoring_version == settings.scoring_version,
                )
            )
            universe: dict[str, dict[str, float | None]] = {}
            for symbol, score in session.execute(stmt):
                # ``factor_scores`` stores one column per dimension, suffixed
                # ``_score`` (technical_score, momentum_score, …).
                universe[str(symbol)] = {
                    factor: _f(getattr(score, f"{factor}_score")) for factor in FACTOR_COLUMNS
                }

        rankings = score_universe(universe)
        return [
            to_ranking_payload(ranking, rank, len(rankings))
            for rank, ranking in enumerate(rankings, start=1)
        ]

    def get_ranking(self, symbol: str) -> dict[str, Any] | None:
        wanted = symbol.upper()
        for row in self.get_ranked():
            if row["symbol"] == wanted:
                return row
        return None

    # ------------------------------------------------- fundamentals/technical
    def get_indicators(self, symbol: str) -> dict[str, Any] | None:
        """Full §2.4 indicator set computed as-of the latest stored bar.

        The engine (``src/market/technical``) exposes MACD, Bollinger, ATR and
        volume averages; the read path used to publish only SMA20/EMA12/RSI14,
        which made the dashboard page look wrong (T015c).
        """
        prices = self.get_prices(symbol)
        if not prices:
            return None
        closes = [float(str(row["close"])) for row in prices]
        highs = [float(str(row["high"])) for row in prices]
        lows = [float(str(row["low"])) for row in prices]
        volumes = [int(float(str(row["volume"]))) for row in prices]

        macd_line, macd_signal, macd_hist = tech.macd(closes)
        bb_upper, bb_mid, bb_lower = tech.bollinger_bands(closes)
        last = -1
        series: dict[str, float | None] = {
            "close": closes[last],
            "sma20": tech.sma(closes, 20)[last],
            "sma50": tech.sma(closes, 50)[last],
            "ema12": tech.ema(closes, 12)[last],
            "ema26": tech.ema(closes, 26)[last],
            "rsi14": tech.rsi(closes, 14)[last],
            "macd": macd_line[last],
            "macd_signal": macd_signal[last],
            "macd_hist": macd_hist[last],
            "bb_upper": bb_upper[last],
            "bb_middle": bb_mid[last],
            "bb_lower": bb_lower[last],
            "atr14": tech.atr(highs, lows, closes, 14)[last],
            "volume_sma20": tech.volume_sma(volumes, 20)[last],
        }
        sma20 = series["sma20"]
        series["price_vs_sma20"] = (
            round(closes[last] / sma20 - 1.0, 6) if sma20 else None
        )
        return {
            "symbol": symbol.upper(),
            "as_of": prices[-1]["trade_date"],
            "series": series,
        }

    def get_features(self, symbol: str) -> dict[str, Any]:
        """Persisted feature rows for the newest feature version (empty when none)."""
        payload: dict[str, Any] = {
            "symbol": symbol.upper(),
            "feature_version": "baseline_1.0",
            "rows": [],
        }
        with self._scope() as session:
            stock_id = self._stock_id(session, symbol)
            if stock_id is None:
                return payload
            latest = session.scalar(
                select(func.max(Feature.trade_date)).where(Feature.stock_id == stock_id)
            )
            if latest is None:
                return payload
            version = session.scalar(
                select(Feature.feature_version)
                .where(Feature.stock_id == stock_id, Feature.trade_date == latest)
                .order_by(Feature.feature_version.desc())
                .limit(1)
            )
            stmt = (
                select(Feature)
                .where(
                    Feature.stock_id == stock_id,
                    Feature.trade_date == latest,
                    Feature.feature_version == version,
                )
                .order_by(Feature.feature_name.asc())
            )
            payload["feature_version"] = version or "baseline_1.0"
            payload["rows"] = [
                {
                    "trade_date": feature.trade_date,
                    "feature_name": feature.feature_name,
                    "value": float(feature.value),
                    "feature_version": feature.feature_version,
                }
                for feature in session.scalars(stmt)
            ]
        return payload

    def get_valuation_summary(self, symbol: str) -> dict[str, Any] | None:
        with self._scope() as session:
            stock_id = self._stock_id(session, symbol)
            if stock_id is None:
                return None
            stmt = (
                select(ValuationDaily)
                .where(ValuationDaily.stock_id == stock_id)
                .order_by(ValuationDaily.trade_date.desc())
                .limit(1)
            )
            row = session.scalars(stmt).first()
            if row is None:
                return None
            return {
                "symbol": symbol.upper(),
                "trade_date": row.trade_date,
                "pe": _f(row.pe),
                "pb": _f(row.pb),
                "ev_ebitda": _f(row.ev_ebitda),
                "dividend_yield": _f(row.dividend_yield),
                "peg": _f(row.peg),
                "industry_pe_median": _f(row.industry_pe_median),
            }

    def get_valuation_history(self, symbol: str) -> list[dict[str, Any]]:
        """Daily valuation snapshots, newest first."""
        with self._scope() as session:
            stock_id = self._stock_id(session, symbol)
            if stock_id is None:
                return []
            stmt = (
                select(ValuationDaily)
                .where(ValuationDaily.stock_id == stock_id)
                .order_by(ValuationDaily.trade_date.desc())
                .limit(HISTORY_LIMIT)
            )
            return [
                {"trade_date": row.trade_date, "pe": _f(row.pe), "pb": _f(row.pb)}
                for row in session.scalars(stmt)
            ]

    def get_quality(self, symbol: str) -> dict[str, Any] | None:
        """Latest quality score for the symbol, else the latest dataset-level row.

        ``src/data/pipelines.py`` scores a *batch* (``stock_id IS NULL``), so a
        per-stock row often does not exist — falling back to the dataset score is
        the honest answer (§39 scores datasets).
        """
        with self._scope() as session:
            stock_id = self._stock_id(session, symbol)
            if stock_id is None:
                return None

            per_stock = (
                select(DataQualityScore)
                .where(DataQualityScore.stock_id == stock_id)
                .order_by(DataQualityScore.as_of_date.desc())
                .limit(1)
            )
            row = session.scalars(per_stock).first()
            if row is None:
                dataset = (
                    select(DataQualityScore)
                    .where(
                        DataQualityScore.stock_id.is_(None),
                        DataQualityScore.dataset == "prices",
                    )
                    .order_by(DataQualityScore.as_of_date.desc())
                    .limit(1)
                )
                row = session.scalars(dataset).first()
            if row is None:
                return None
            return {
                "symbol": symbol.upper(),
                "as_of_date": row.as_of_date,
                "overall_score": _f(row.overall_score) or 0.0,
                "below_threshold": bool(row.below_threshold),
                "dimensions": {
                    name: _f(getattr(row, name))
                    for name in (
                        "completeness",
                        "validity",
                        "consistency",
                        "uniqueness",
                        "freshness",
                        "accuracy",
                    )
                },
            }

    def get_statements(self, symbol: str) -> list[dict[str, Any]]:
        """Statement line items grouped into periods (bitemporal: current rows only)."""
        with self._scope() as session:
            stock_id = self._stock_id(session, symbol)
            if stock_id is None:
                return []
            stmt = (
                select(FinancialStatement)
                .where(
                    FinancialStatement.stock_id == stock_id,
                    FinancialStatement.valid_to.is_(None),
                )
                .order_by(
                    FinancialStatement.fiscal_year.desc(),
                    FinancialStatement.fiscal_period.desc(),
                    FinancialStatement.line_item.asc(),
                )
            )
            grouped: dict[tuple[str, int, int, str], dict[str, Any]] = {}
            for row in session.scalars(stmt):
                key = (row.period_type, row.fiscal_year, row.fiscal_period, row.statement_type)
                entry = grouped.setdefault(
                    key,
                    {
                        "period_end": _period_end(
                            row.period_type, row.fiscal_year, row.fiscal_period
                        ),
                        "statement_type": row.statement_type.lower(),
                        "currency": row.currency,
                        "items": {},
                    },
                )
                items: dict[str, float] = entry["items"]
                items[row.line_item] = float(row.value)
        return sorted(grouped.values(), key=lambda entry: entry["period_end"], reverse=True)

    def get_ratios(self, symbol: str) -> list[dict[str, Any]]:
        """Deterministic ratio rows, newest period first."""
        with self._scope() as session:
            stock_id = self._stock_id(session, symbol)
            if stock_id is None:
                return []
            stmt = select(FinancialRatio).where(FinancialRatio.stock_id == stock_id)
            rows = [
                {
                    "period_end": _period_end(
                        row.period_type, row.fiscal_year, row.fiscal_period
                    ),
                    "name": row.ratio_name.lower(),
                    "value": float(row.value),
                }
                for row in session.scalars(stmt)
            ]
        rows.sort(key=lambda row: (row["period_end"], str(row["name"])), reverse=True)
        return rows

    # ------------------------------------------------------------------ news
    def list_news(self) -> list[dict[str, Any]]:
        """News items with their linked symbols, newest first."""
        with self._scope() as session:
            stmt = select(News).order_by(News.published_at.desc()).limit(DEFAULT_LIMIT)
            items = list(session.scalars(stmt))
            if not items:
                return []

            news_ids = [item.id for item in items]
            links = session.execute(
                select(NewsSymbol.news_id, Stock.symbol)
                .join(Stock, NewsSymbol.stock_id == Stock.id)
                .where(NewsSymbol.news_id.in_(news_ids))
            ).all()
            by_news: dict[int, list[str]] = {}
            for news_id, symbol in links:
                by_news.setdefault(news_id, []).append(symbol)

            return [
                {
                    "id": item.id,
                    "title": item.title,
                    "source": item.source,
                    "published_at": item.published_at,
                    "symbols": by_news.get(item.id, []),
                }
                for item in items
            ]

    # ------------------------------------------------------------- backtests
    @staticmethod
    def _parse_backtest_id(bt_id: str) -> UUID | None:
        try:
            return UUID(bt_id)
        except (ValueError, AttributeError, TypeError):
            return None

    @staticmethod
    def _backtest_row(row: Backtest) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "strategy_name": row.strategy_name,
            "strategy_version": row.strategy_version,
            "universe": row.universe,
            "start_date": row.start_date,
            "end_date": row.end_date,
            "run_type": row.run_type,
            "transaction_cost_bps": float(row.transaction_cost_bps),
            "slippage_bps": float(row.slippage_bps),
        }

    def get_backtest(self, bt_id: str) -> dict[str, Any] | None:
        backtest_id = self._parse_backtest_id(bt_id)
        if backtest_id is None:
            return None
        with self._scope() as session:
            row = session.get(Backtest, backtest_id)
            return self._backtest_row(row) if row is not None else None

    def list_backtests(self) -> list[dict[str, Any]]:
        stmt = select(Backtest).order_by(Backtest.start_date.desc()).limit(DEFAULT_LIMIT)
        with self._scope() as session:
            return [self._backtest_row(row) for row in session.scalars(stmt)]

    def get_backtest_metrics(self, bt_id: str) -> list[dict[str, Any]]:
        backtest_id = self._parse_backtest_id(bt_id)
        if backtest_id is None:
            return []
        stmt = (
            select(BacktestMetric)
            .where(BacktestMetric.backtest_id == backtest_id)
            .order_by(BacktestMetric.metric_name.asc())
        )
        with self._scope() as session:
            return [
                {"metric_name": row.metric_name, "value": float(row.value)}
                for row in session.scalars(stmt)
            ]

    def get_backtest_trades(self, bt_id: str) -> list[dict[str, Any]]:
        backtest_id = self._parse_backtest_id(bt_id)
        if backtest_id is None:
            return []
        stmt = (
            select(BacktestTrade, Stock.symbol)
            .join(Stock, BacktestTrade.stock_id == Stock.id)
            .where(BacktestTrade.backtest_id == backtest_id)
            .order_by(BacktestTrade.entry_date.asc())
        )
        with self._scope() as session:
            return [
                {
                    "symbol": symbol,
                    "entry_date": trade.entry_date,
                    "exit_date": trade.exit_date,
                    "entry_price": float(trade.entry_price),
                    "exit_price": _f(trade.exit_price),
                    "quantity": float(trade.quantity),
                    "pnl": _f(trade.pnl),
                    "return_pct": _f(trade.return_pct),
                }
                for trade, symbol in session.execute(stmt)
            ]


__all__ = ["DbMarketService", "DEFAULT_LIMIT", "HISTORY_LIMIT", "FACTOR_COLUMNS"]
