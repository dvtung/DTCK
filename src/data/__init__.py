"""DTCK data foundation: collectors, validators, normalizers, pipelines, quality.

Public API (T004/T005):

- ``create_provider`` / ``provider_specs`` — registry-backed provider selection
- ``collect_eod`` / ``collect_index`` / ``collect_news`` — raw collection
- ``validate_*`` / ``normalize_*`` — quality-first transforms
- ``ingest_eod`` / ``ingest_index`` / ``ingest_news`` — end-to-end pipelines
- ``compute_quality`` / ``persist_quality`` — spec §39 scoring + gate (T005)
"""

from src.data.collectors import (
    collect_eod,
    collect_events,
    collect_financials,
    collect_index,
    collect_news,
)
from src.data.normalizers import (
    normalize_eod,
    normalize_events,
    normalize_financials,
    normalize_index,
    normalize_news,
    resolve_stock_ids,
)
from src.data.pipelines import (
    IngestResult,
    ingest_eod,
    ingest_events,
    ingest_financials,
    ingest_index,
    ingest_news,
)
from src.data.providers import (
    DataProvider,
    FixtureProvider,
    HttpJsonProvider,
    YahooChartProvider,
    create_provider,
    enabled_by_role,
    fallback_chain,
    financial_provider_chain,
    get_spec,
    market_provider_chain,
    provider_specs,
)
from src.data.quality import QualityScore, compute_quality, persist_quality
from src.data.validators import (
    ValidationIssue,
    validate_eod,
    validate_events,
    validate_financials,
    validate_index,
    validate_news,
)

__all__ = [
    "DataProvider",
    "FixtureProvider",
    "HttpJsonProvider",
    "YahooChartProvider",
    "create_provider",
    "provider_specs",
    "enabled_by_role",
    "fallback_chain",
    "market_provider_chain",
    "get_spec",
    "collect_eod",
    "collect_events",
    "collect_financials",
    "collect_index",
    "collect_news",
    "ValidationIssue",
    "validate_eod",
    "validate_events",
    "validate_financials",
    "validate_index",
    "validate_news",
    "normalize_eod",
    "normalize_events",
    "normalize_financials",
    "normalize_index",
    "normalize_news",
    "resolve_stock_ids",
    "IngestResult",
    "ingest_eod",
    "ingest_events",
    "ingest_financials",
    "ingest_index",
    "ingest_news",
    "financial_provider_chain",
    "QualityScore",
    "compute_quality",
    "persist_quality",
]
