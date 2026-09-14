"""Unit tests for the STEP 2 database design: models metadata + seeds + migration contract.

These tests run **without** a database connection: they validate the schema
*source of truth* (SQLAlchemy models), the seed data integrity, and the initial
migration's hypertable contract.
"""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

from sqlalchemy import UniqueConstraint

EXPECTED_TABLES = {
    "exchanges",
    "sectors",
    "industries",
    "stocks",
    "prices",
    "adjusted_prices",
    "index_prices",
    "foreign_flows",
    "prop_trading_flows",
    "financial_statements",
    "financial_ratios",
    "valuation_daily",
    "corporate_events",
    "news",
    "news_symbols",
    "macro_indicators",
    "features",
    "factor_scores",
    "signals",
    "market_regimes",
    "model_registry",
    "predictions",
    "prediction_evaluations",
    "backtests",
    "backtest_trades",
    "backtest_metrics",
    "documents",
    "evidence",
    "agent_registry",
    "agent_runs",
    "agent_tool_calls",
    "portfolios",
    "portfolio_positions",
    "portfolio_snapshots",
    "audit_logs",
    "data_quality_scores",
    "users",
    "api_keys",
}


def _load_initial_migration() -> types.ModuleType:
    """Load the initial migration module by file path (versions/ has no package)."""
    path = (
        Path(__file__).resolve().parents[2]
        / "database"
        / "migrations"
        / "versions"
        / "0001_initial_schema.py"
    )
    spec = importlib.util.spec_from_file_location("dtck_m0001", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_models_metadata_has_all_expected_tables() -> None:
    from src.common.models import Base

    assert EXPECTED_TABLES <= set(Base.metadata.tables)


def test_predictions_is_regular_table_not_hypertable() -> None:
    """Documented deviation: predictions stays a regular table (FK target)."""
    from src.common.models import Base

    assert "predictions" in Base.metadata.tables


def test_migration_hypertables_match_models() -> None:
    from src.common.models import Base

    migration = _load_initial_migration()
    for table_name, (partition_col, _chunk) in migration.HYPERTABLES.items():
        assert table_name in Base.metadata.tables, f"{table_name} missing from models"
        table = Base.metadata.tables[table_name]
        # The partition column must appear in a unique index/constraint so that
        # TimescaleDB can convert the table into a hypertable.
        indexed = {c.name for c in table.primary_key.columns}
        for uq in table.constraints:
            if isinstance(uq, UniqueConstraint):
                indexed |= {c.name for c in uq.columns}
        assert partition_col in indexed, (
            f"partition column {partition_col} of {table_name} must be in a unique index"
        )
    # Documented exclusion: predictions is FK-referenced and cannot be a hypertable.
    assert "predictions" not in migration.HYPERTABLES


def test_seed_exchanges_codes_are_valid() -> None:
    from database.seeds.seed_exchanges import EXCHANGES

    codes = {code for code, _ in EXCHANGES}
    assert codes == {"HOSE", "HNX", "UPCOM"}


def test_seed_sectors_are_well_formed() -> None:
    from database.seeds.seed_sectors import INDUSTRIES, SECTORS

    sector_codes = {code for code, _ in SECTORS}
    assert len(sector_codes) == len(SECTORS)  # no duplicates
    for _code, _name, parent in INDUSTRIES:
        assert parent in sector_codes, f"industry {_code} has unknown parent {parent}"


def test_seed_vn30_has_30_unique_symbols_and_valid_refs() -> None:
    from database.seeds.seed_exchanges import EXCHANGES
    from database.seeds.seed_sectors import INDUSTRIES, SECTORS
    from database.seeds.seed_vn30 import VN30

    symbols = [row[0] for row in VN30]
    assert len(symbols) == 30
    assert len(set(symbols)) == 30  # unique tickers

    exchange_codes = {code for code, _ in EXCHANGES}
    sector_codes = {code for code, _ in SECTORS}
    industry_codes = {code for code, _name, _parent in INDUSTRIES}
    for symbol, _name, exc, sec, ind, is_vn30 in VN30:
        assert exc in exchange_codes, f"{symbol} exchange {exc} unknown"
        assert sec in sector_codes, f"{symbol} sector {sec} unknown"
        assert ind in industry_codes, f"{symbol} industry {ind} unknown"
        assert is_vn30 is True


def test_seed_vn30_flags_expect_true() -> None:
    """Every seeded universe row must carry is_vn30=True for the MVP baseline."""
    from database.seeds.seed_vn30 import VN30

    assert all(row[5] for row in VN30)
