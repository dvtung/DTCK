"""API response schemas for /api/v1 (docs/API_SPECIFICATION.md).

Conventions: JSON with `{ "error": { code, message, details } }` for errors,
and paginated `{ items, total, limit, offset }` envelopes.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TypeVar
from uuid import UUID

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


# --------------------------------------------------------------- agent API


class LoginRequest(BaseModel):
    """POST /api/v1/auth/login."""

    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class AnalysisRequest(BaseModel):
    """POST /api/v1/agents/analyze + /api/v1/analysis/request (§2.7/§2.11)."""

    symbol: str = Field(min_length=1, max_length=16)
    user_request: str | None = None


class ResearchRequest(BaseModel):
    """POST /api/v1/agents/research (§20.1)."""

    symbol: str = Field(min_length=1, max_length=16)
    query: str | None = None
    user_request: str | None = None


class MonitorRequest(BaseModel):
    """POST /api/v1/agents/monitor (§20.3)."""

    symbols: list[str] = Field(min_length=1, max_length=50)
    previous_signals: dict[str, str] | None = None
    user_request: str | None = None


class PositionIn(BaseModel):
    """One portfolio position (§20.4/§27)."""

    symbol: str = Field(min_length=1, max_length=16)
    quantity: float = Field(gt=0)
    cost_basis: float | None = None


class PortfolioRequest(BaseModel):
    """POST /api/v1/agents/portfolio (§20.4/§27)."""

    positions: list[PositionIn] = Field(min_length=1, max_length=100)
    risk_budget_annual_vol: float | None = Field(default=None, gt=0)
    user_request: str | None = None


class AgentRunAcceptedOut(BaseModel):
    """202 response of the async analysis pattern (§2.7/§45)."""

    agent_run_id: UUID
    status: str


__all__ = [
    "AgentRunAcceptedOut",
    "AnalysisRequest",
    "BacktestMetricOut",
    "LoginRequest",
    "BacktestOut",
    "BacktestTradeOut",
    "BreadthOut",
    "ErrorBody",
    "ErrorResponse",
    "FactorContributionOut",
    "HealthOut",
    "IndexPriceOut",
    "IndicatorSeries",
    "MonitorRequest",
    "NewsOut",
    "Page",
    "PortfolioRequest",
    "PositionIn",
    "PriceRow",
    "QualityOut",
    "RankingOut",
    "RatioOut",
    "ReadyOut",
    "RegimeOut",
    "ResearchRequest",
    "StatementOut",
    "StockOut",
    "ValuationSummaryOut",
]
