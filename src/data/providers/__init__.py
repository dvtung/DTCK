"""Provider sub-package: base contract, registry, offline + HTTP/RSS implementations."""

from src.data.providers.base import DataProvider
from src.data.providers.cafef_financials import CafefFinancialProvider
from src.data.providers.fixture import FixtureProvider
from src.data.providers.http_json import HttpJsonProvider
from src.data.providers.imf_macro import ImfMacroProvider
from src.data.providers.registry import (
    ProviderSpec,
    create_provider,
    enabled_by_role,
    fallback_chain,
    financial_provider_chain,
    get_spec,
    load_registry,
    market_provider_chain,
    provider_specs,
)
from src.data.providers.rss import RssNewsProvider
from src.data.providers.ssi import SSIFastConnectProvider
from src.data.providers.vndirect_financials import VNDirectFinancialProvider
from src.data.providers.yahoo_chart import YahooChartProvider

__all__ = [
    "CafefFinancialProvider",
    "DataProvider",
    "FixtureProvider",
    "HttpJsonProvider",
    "ImfMacroProvider",
    "ProviderSpec",
    "RssNewsProvider",
    "SSIFastConnectProvider",
    "VNDirectFinancialProvider",
    "YahooChartProvider",
    "create_provider",
    "enabled_by_role",
    "fallback_chain",
    "financial_provider_chain",
    "get_spec",
    "load_registry",
    "market_provider_chain",
    "provider_specs",
]
