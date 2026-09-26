"""Provider sub-package: base contract, registry, offline + HTTP/RSS implementations."""

from src.data.providers.base import DataProvider
from src.data.providers.fixture import FixtureProvider
from src.data.providers.http_json import HttpJsonProvider
from src.data.providers.registry import (
    ProviderSpec,
    create_provider,
    enabled_by_role,
    fallback_chain,
    get_spec,
    load_registry,
    market_provider_chain,
    provider_specs,
)
from src.data.providers.rss import RssNewsProvider
from src.data.providers.ssi import SSIFastConnectProvider
from src.data.providers.yahoo_chart import YahooChartProvider

__all__ = [
    "DataProvider",
    "FixtureProvider",
    "HttpJsonProvider",
    "ProviderSpec",
    "RssNewsProvider",
    "SSIFastConnectProvider",
    "YahooChartProvider",
    "create_provider",
    "enabled_by_role",
    "fallback_chain",
    "get_spec",
    "load_registry",
    "market_provider_chain",
    "provider_specs",
]
