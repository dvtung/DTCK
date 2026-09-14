"""DTCK SQLAlchemy models — the schema source of truth (STEP 2 / DATABASE DESIGN).

Importing this package registers every table on ``Base.metadata`` so that the
initial Alembic migration can create the full schema and the TimescaleDB
hypertables (see ``database/migrations/versions/``).
"""

from src.common.models import (  # noqa: F401  (register tables on metadata)
    agents,
    auth,
    backtest,
    events,
    evidence,
    fundamental,
    governance,
    macro,
    market,
    ml,
    portfolio,
    quant,
    reference,
)

# Public re-exports for application code.
from src.common.models.agents import AgentRegistry, AgentRun, AgentToolCall
from src.common.models.auth import ApiKey, User
from src.common.models.backtest import Backtest, BacktestMetric, BacktestTrade
from src.common.models.base import NAMING_CONVENTION, TIMESTAMPTZ, Base
from src.common.models.events import CorporateEvent, News, NewsSymbol
from src.common.models.evidence import Document, Evidence
from src.common.models.fundamental import FinancialRatio, FinancialStatement
from src.common.models.governance import AuditLog, DataQualityScore
from src.common.models.macro import MacroIndicator
from src.common.models.market import (
    AdjustedPrice,
    ForeignFlow,
    IndexPrice,
    Price,
    PropTradingFlow,
    ValuationDaily,
)
from src.common.models.ml import ModelRegistry, Prediction, PredictionEvaluation
from src.common.models.portfolio import Portfolio, PortfolioPosition, PortfolioSnapshot
from src.common.models.quant import FactorScore, Feature, MarketRegime, Signal
from src.common.models.reference import Exchange, Industry, Sector, Stock

__all__ = [
    "Base",
    "NAMING_CONVENTION",
    "TIMESTAMPTZ",
    "Exchange",
    "Sector",
    "Industry",
    "Stock",
    "Price",
    "AdjustedPrice",
    "IndexPrice",
    "ForeignFlow",
    "PropTradingFlow",
    "ValuationDaily",
    "FinancialStatement",
    "FinancialRatio",
    "CorporateEvent",
    "News",
    "NewsSymbol",
    "MacroIndicator",
    "Feature",
    "FactorScore",
    "Signal",
    "MarketRegime",
    "ModelRegistry",
    "Prediction",
    "PredictionEvaluation",
    "Backtest",
    "BacktestTrade",
    "BacktestMetric",
    "Document",
    "Evidence",
    "AgentRegistry",
    "AgentRun",
    "AgentToolCall",
    "Portfolio",
    "PortfolioPosition",
    "PortfolioSnapshot",
    "AuditLog",
    "DataQualityScore",
    "User",
    "ApiKey",
]
