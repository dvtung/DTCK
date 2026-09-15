"""In-memory market data service used by the MVP-1 read API.

Deterministic, DB-free so the API is unit-testable and runs without a live
TimescaleDB. Data is synthetic but aligned with the seeded reference data
(exchanges, VN30 universe) and produced by the deterministic engine functions.

Swap this implementation for a SQLAlchemy-backed repository when the persistence
layer goes live — the router contracts do not change.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from src.market.technical import indicators as tech
from src.quant.scoring.engine import StockRanking, score_universe

BASE_STOCKS: dict[str, tuple[str, str, str, bool]] = {
    "FPT": ("FPT Corporation", "TECH", "Technology", True),
    "VCB": ("Vietcombank", "FIN", "Banks", True),
    "VNM": ("Vinamilk", "CONS", "Food Products", True),
    "VIC": ("Vingroup JSC", "REAL", "Real Estate", True),
    "HPG": ("Hoa Phat Group", "MAT", "Steel", True),
    "BID": ("BIDV", "FIN", "Banks", True),
    "TCB": ("Techcombank", "FIN", "Banks", True),
}


class MarketService:
    """In-memory deterministic market store for MVP-1 read endpoints."""

    def __init__(self) -> None:
        self._dates = self._business_days(date(2026, 6, 1), 60)
        self._stocks: dict[str, dict[str, object]] = {}
        for idx, (sym, (name, sec, ind, is_vn30)) in enumerate(BASE_STOCKS.items()):
            base = Decimal("100") + Decimal(idx) * Decimal("2.0")
            self._stocks[sym] = {
                "symbol": sym,
                "company_name": name,
                "exchange": "HOSE",
                "sector": sec,
                "industry": ind,
                "listed_date": date(2006, 1, 1),
                "status": "ACTIVE",
                "is_vn30": is_vn30,
                "seed_price": base,
            }
        self._prices: dict[str, list[dict[str, object]]] = {
            s: self._make_prices(float(str(m["seed_price"]))) for s, m in self._stocks.items()
        }
        self._index_prices: dict[str, list[dict[str, object]]] = {
            "VNINDEX": self._make_prices(1200.0),
            "VN30": self._make_prices(1300.0),
        }
        self._scores = self._make_scores()
        self._quality = self._make_quality()
        self._valuation = self._make_valuation()
        self._news = self._make_news()
        self._backtests = self._make_backtests()
        self._regime = {"regime": "BULL", "confidence": 0.72, "trade_date": self._dates[-1]}

    @staticmethod
    def _business_days(start: date, count: int) -> list[date]:
        out: list[date] = []
        d = start
        while len(out) < count:
            if d.weekday() < 5:  # Mon-Fri
                out.append(d)
            d = d.fromordinal(d.toordinal() + 1)
        return out

    def _make_prices(self, base: float) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        price = base
        for i, d in enumerate(self._dates):
            close = price * (1.005 + ((i % 3) - 1) * 0.002)
            high = max(price, close) * 1.008
            low = min(price, close) * 0.992
            rows.append(
                {
                    "trade_date": d,
                    "open": round(price, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "close": round(close, 2),
                    "volume": int(500_000 + i * 1_000),
                }
            )
            price = close
        return rows

    # ---------------------------------------------------------- market
    def list_indices(self) -> list[dict[str, object]]:
        return [{"index_code": code, **rows[-1]} for code, rows in self._index_prices.items()]

    def get_index(self, code: str) -> dict[str, object] | None:
        rows = self._index_prices.get(code)
        return dict(rows[-1]) if rows else None

    def get_regime(self) -> dict[str, object]:
        return dict(self._regime)

    def get_breadth(self) -> dict[str, object]:
        return {
            "trade_date": self._dates[-1],
            "advancers": 18,
            "decliners": 9,
            "unchanged": 3,
            "participation": 0.82,
        }

    # ---------------------------------------------------------- stocks
    def list_stocks(
        self, exchange: str | None, sector: str | None, vn30: bool | None
    ) -> list[dict[str, object]]:
        out = []
        for sym, meta in self._stocks.items():
            if exchange and meta["exchange"] != exchange:
                continue
            if sector and meta["sector"] != sector:
                continue
            if vn30 and not meta["is_vn30"]:
                continue
            out.append({**meta, "price": self._prices[sym][-1]["close"]})
        return sorted(out, key=lambda r: str(r["symbol"]))

    def get_stock(self, symbol: str) -> dict[str, object] | None:
        meta = self._stocks.get(symbol)
        if not meta:
            return None
        return {**meta, "price": self._prices[symbol][-1]["close"]}

    def get_prices(self, symbol: str) -> list[dict[str, object]] | None:
        return self._prices.get(symbol)

    # ---------------------------------------------------------- ranking
    def get_ranking(self, symbol: str) -> dict[str, object] | None:
        for r in self.get_ranked():
            if r["symbol"] == symbol:
                return dict(r)
        return None

    def get_ranked(self) -> list[dict[str, object]]:
        universe: dict[str, dict[str, float | None]] = {}
        symbols = list(self._stocks)
        for i, sym in enumerate(symbols):
            values = {
                "fundamental": 35.0 + i,
                "technical": 40.0 + i,
                "momentum": 45.0 + i,
                "valuation": 30.0 + i,
                "quality": 50.0 + i,
                "risk": 20.0 + i,
            }
            universe[sym] = {k: float(v) for k, v in values.items()}
        rankings = score_universe(universe)
        return [self._to_ranking(r, i, len(rankings)) for i, r in enumerate(rankings, start=1)]

    @staticmethod
    def _to_ranking(r: StockRanking, i: int, total: int) -> dict[str, object]:
        return {
            "symbol": r.stock_id,
            "overall_score": round(r.overall_score, 2) if r.overall_score is not None else None,
            "signal": r.signal,
            "confidence": r.confidence,
            "rank": i,
            "total": total,
            "contributions": [
                {
                    "factor": c.factor,
                    "score": c.score,
                    "weight": c.weight,
                    "weighted_score": round(c.weighted_score, 4),
                    "contribution_pct": round(c.contribution_pct, 4)
                        if c.contribution_pct is not None
                        else None,
                }
                for c in r.decomposition.contributions
            ],
        }

    # -------------------------------------------------- fundamentals/tech
    def get_indicators(self, symbol: str) -> dict[str, object] | None:
        rows = self._prices.get(symbol)
        if not rows:
            return None
        closes = [float(str(r["close"])) for r in rows]
        return {
            "symbol": symbol,
            "as_of": rows[-1]["trade_date"],
            "series": {
                "sma20": tech.sma(closes, 20)[-1],
                "ema12": tech.ema(closes, 12)[-1],
                "rsi14": tech.rsi(closes, 14)[-1],
            },
        }

    def get_valuation_summary(self, symbol: str) -> dict[str, object] | None:
        if symbol not in self._stocks:
            return None
        return {"symbol": symbol, "trade_date": self._dates[-1], **self._valuation.get(symbol, {})}

    def get_quality(self, symbol: str) -> dict[str, object] | None:
        if symbol not in self._stocks:
            return None
        return {"symbol": symbol, "as_of_date": self._dates[-1], **self._quality.get(symbol, {})}

    # ---------------------------------------------------------- news
    def list_news(self) -> list[dict[str, object]]:
        return self._news

    # -------------------------------------------------------- backtests
    def get_backtest(self, bt_id: str) -> dict[str, object] | None:
        return self._backtests.get(bt_id)

    def list_backtests(self) -> list[dict[str, object]]:
        return list(self._backtests.values())

    def get_backtest_metrics(self, bt_id: str) -> list[dict[str, object]]:
        if bt_id not in self._backtests:
            return []
        return [
            {"metric_name": "total_return", "value": 0.182},
            {"metric_name": "cagr", "value": 0.141},
            {"metric_name": "sharpe_ratio", "value": 1.32},
            {"metric_name": "max_drawdown", "value": -0.11},
            {"metric_name": "win_rate", "value": 0.58},
            {"metric_name": "profit_factor", "value": 1.41},
        ]

    def get_backtest_trades(self, bt_id: str) -> list[dict[str, object]]:
        if bt_id != "bt-001":
            return []
        return [
            {"symbol": "FPT", "entry_date": self._dates[2], "exit_date": self._dates[10],
             "entry_price": 105.0, "exit_price": 112.5, "quantity": 100, "pnl": 750.0,
             "return_pct": 0.071},
            {"symbol": "VCB", "entry_date": self._dates[3], "exit_date": self._dates[11],
             "entry_price": 96.0, "exit_price": 98.4, "quantity": 150, "pnl": 360.0,
             "return_pct": 0.025},
        ]

    # ---------------------------------------------------------- seed data
    def _make_quality(self) -> dict[str, dict[str, object]]:
        dims = {"completeness": 95, "validity": 90, "consistency": 94,
                "uniqueness": 100, "freshness": 88, "accuracy": 91}
        return {s: {"overall_score": 92.0, "below_threshold": False, "dimensions": dict(dims)}
                for s in self._stocks}

    def _make_valuation(self) -> dict[str, dict[str, object]]:
        return {s: {"pe": round(12.5 + i, 2), "pb": round(2.1 + i * 0.1, 2),
                    "ev_ebitda": round(9.0 + i, 2), "dividend_yield": 0.03,
                    "peg": 1.2, "industry_pe_median": 11.0}
                for i, s in enumerate(self._stocks)}

    def _make_news(self) -> list[dict[str, object]]:
        return [
            {"id": 3, "title": "VNINDEX adjustments continue", "source": "cafef",
             "published_at": datetime(2026, 9, 3, 8, 0), "url": None},
            {"id": 2, "title": "Banks lift the market", "source": "vnexpress",
             "published_at": datetime(2026, 9, 2, 9, 30), "url": None},
            {"id": 1, "title": "Foreign flows turn positive", "source": "vietstock",
             "published_at": datetime(2026, 9, 1, 10, 15), "url": None},
        ]

    def _make_scores(self) -> dict[str, object]:
        return {}

    def _make_backtests(self) -> dict[str, dict[str, object]]:
        return {
            "bt-001": {
                "id": "bt-001",
                "strategy_name": "baseline_multi_factor",
                "strategy_version": "0.1.0",
                "universe": "VN30",
                "start_date": self._dates[0],
                "end_date": self._dates[-1],
                "run_type": "walk-forward",
                "transaction_cost_bps": 15.0,
                "slippage_bps": 5.0,
            }
        }
