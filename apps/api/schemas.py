"""API response schemas for /api/v1 (docs/API_SPECIFICATION.md).

Conventions: JSON with `{ "error": { code, message, details } }` for errors,
and paginated `{ items, total, limit, offset }` envelopes.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorBody(BaseModel):
    code: str
    message: str
    details: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class Page[T](BaseModel):
    """Paginated envelope: { items, total, limit, offset }."""
    items: list[T]
    total: int
    limit: int
    offset: int


class IndexPriceOut(BaseModel):
    index_code: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class RegimeOut(BaseModel):
    regime: str
    confidence: float
    trade_date: date


class BreadthOut(BaseModel):
    trade_date: date
    advancers: int
    decliners: int
    unchanged: int
    participation: float | None


class StockOut(BaseModel):
    symbol: str
    company_name: str
    exchange: str
    sector: str | None = None
    industry: str | None = None
    listed_date: date | None = None
    status: str = "ACTIVE"
    is_vn30: bool = False


class PriceRow(BaseModel):
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class FactorContributionOut(BaseModel):
    factor: str
    score: float
    weight: float
    weighted_score: float
    contribution_pct: float | None


class RankingOut(BaseModel):
    symbol: str
    overall_score: float | None
    signal: str
    confidence: float
    rank: int
    total: int
    contributions: list[FactorContributionOut]


class StatementOut(BaseModel):
    period_end: date
    statement_type: str
    currency: str
    items: dict[str, float]


class RatioOut(BaseModel):
    period_end: date
    name: str
    value: float | None


class QualityOut(BaseModel):
    symbol: str
    as_of_date: date
    overall_score: float
    below_threshold: bool
    dimensions: dict[str, float | None]


class IndicatorSeries(BaseModel):
    name: str
    values: list[float | None]


class ValuationSummaryOut(BaseModel):
    symbol: str
    trade_date: date
    pe: float | None
    pb: float | None
    ev_ebitda: float | None
    dividend_yield: float | None
    peg: float | None
    industry_pe_median: float | None


class NewsOut(BaseModel):
    id: int
    title: str
    source: str
    published_at: datetime
    url: str | None = None


class BacktestOut(BaseModel):
    id: str
    strategy_name: str
    strategy_version: str
    universe: str
    start_date: date
    end_date: date
    run_type: str
    transaction_cost_bps: float
    slippage_bps: float


class BacktestMetricOut(BaseModel):
    metric_name: str
    value: float


class BacktestTradeOut(BaseModel):
    symbol: str
    entry_date: date
    exit_date: date | None
    entry_price: float
    exit_price: float | None
    quantity: float
    pnl: float | None
    return_pct: float | None


class HealthOut(BaseModel):
    status: str
    service: str
    version: str


class ReadyOut(BaseModel):
    status: str
    dependencies: dict[str, str]
    as_of: datetime = Field(default_factory=lambda: datetime.now())


__all__ = [
    "ErrorBody", "ErrorResponse", "Page", "IndexPriceOut", "RegimeOut", "BreadthOut",
    "StockOut", "PriceRow", "FactorContributionOut", "RankingOut", "StatementOut",
    "RatioOut", "QualityOut", "IndicatorSeries", "ValuationSummaryOut", "NewsOut",
    "BacktestOut", "BacktestMetricOut", "BacktestTradeOut", "HealthOut", "ReadyOut",
]
