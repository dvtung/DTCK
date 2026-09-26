"""Provider registry — loads the machine-readable contract from ``configs/sources.yaml``.

This is the runtime half of the T002 design (``docs/DATA_SOURCES.md`` §3): ids,
roles, auth model, credential env-var names, enabled/priority flags and fallback
chains live in config; secrets never do (spec §32).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from src.data.providers.base import DataProvider
from src.data.providers.fixture import FixtureProvider
from src.data.providers.http_json import HttpJsonProvider
from src.data.providers.rss import DEFAULT_USER_AGENT, RssNewsProvider
from src.data.providers.ssi import SSIFastConnectProvider
from src.data.providers.yahoo_chart import YahooChartProvider

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SOURCES_PATH = REPO_ROOT / "configs" / "sources.yaml"


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    """One provider entry from ``configs/sources.yaml``."""

    id: str
    description: str
    roles: tuple[str, ...]
    auth: str
    credential_env: str
    enabled: bool
    priority: int
    licensed: bool
    free: bool
    endpoints: dict[str, Any] = field(default_factory=dict)
    endpoints_status: str = "unknown"


def load_registry(path: Path | str | None = None) -> dict[str, Any]:
    """Parse ``configs/sources.yaml`` (or an explicit override path)."""
    with Path(path or DEFAULT_SOURCES_PATH).open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"invalid sources registry: {path or DEFAULT_SOURCES_PATH}")
    return data


def provider_specs(path: Path | str | None = None) -> list[ProviderSpec]:
    """Return every provider in the registry as a validated ``ProviderSpec``."""
    raw = load_registry(path)
    specs: list[ProviderSpec] = []
    for entry in raw.get("providers", []):
        specs.append(
            ProviderSpec(
                id=str(entry["id"]),
                description=str(entry.get("description", "")),
                roles=tuple(entry.get("roles", ())),
                auth=str(entry.get("auth", "none")),
                credential_env=str(entry.get("credential_env", "")),
                enabled=bool(entry.get("enabled", False)),
                priority=int(entry.get("priority", 0)),
                licensed=bool(entry.get("licensed", False)),
                free=bool(entry.get("free", True)),
                endpoints=dict(entry.get("endpoints", {}) or {}),
                endpoints_status=str(entry.get("endpoints_status", "unknown")),
            )
        )
    return specs


def get_spec(provider_id: str, path: Path | str | None = None) -> ProviderSpec:
    """Look up one provider spec, raising a clear error when unknown."""
    for spec in provider_specs(path):
        if spec.id == provider_id:
            return spec
    known = ", ".join(s.id for s in provider_specs(path))
    raise KeyError(f"unknown data provider '{provider_id}' (known: {known})")


def enabled_by_role(role: str, path: Path | str | None = None) -> list[ProviderSpec]:
    """Enabled providers serving ``role``, highest priority first."""
    return sorted(
        (s for s in provider_specs(path) if s.enabled and role in s.roles),
        key=lambda s: s.priority,
        reverse=True,
    )


def fallback_chain(role: str, path: Path | str | None = None) -> list[str]:
    """Fallback provider ids for ``role`` (registry `fallback_chains`)."""
    return list(load_registry(path).get("fallback_chains", {}).get(role, []))


def market_provider_chain(
    primary: str | None = None,
    path: Path | str | None = None,
) -> list[str]:
    """Market EOD chain to try in order: primary first, then the fallbacks.

    ``primary`` overrides ``selection.market`` (e.g. ``SCHEDULER_EOD_SOURCE``);
    a provider only appears once, so a misconfigured primary that also sits in
    ``fallback_chains.market`` cannot be retried in the same run.
    """
    selection = load_registry(path).get("selection", {}) or {}
    configured = primary or str(selection.get("market", ""))
    chain: list[str] = []
    if configured and configured != "computed":
        chain.append(configured)
    for provider_id in fallback_chain("market", path):
        if provider_id not in chain:
            chain.append(provider_id)
    return chain


def _credential_value(spec: ProviderSpec) -> str | None:
    """Resolve the secret referenced by ``spec.credential_env`` (never logged)."""
    if not spec.credential_env:
        return None
    return os.getenv(spec.credential_env) or None


def create_provider(
    provider_id: str,
    *,
    path: Path | str | None = None,
    fixture_eod: list[Any] | None = None,
    fixture_index: list[Any] | None = None,
    fixture_news: list[Any] | None = None,
    http_timeout: float | None = None,
    max_retries: int | None = None,
    transport: Any | None = None,
    universe: frozenset[str] = frozenset(),
) -> DataProvider:
    """Build a provider instance for ``provider_id``.

    ``fixture_*`` rows create an offline :class:`FixtureProvider` (tests, demos,
    backfills without network). A verified ``endpoints.news`` block builds an
    :class:`RssNewsProvider` (news feeds are standard RSS — no field mapping
    needed). Otherwise an :class:`HttpJsonProvider` is built from the registry's
    ``endpoints.eod`` block; ``endpoints.eod.client: yahoo_chart`` selects the
    :class:`YahooChartProvider` (parallel-array payload + split un-adjustment).
    ``universe`` is the set of reference symbols used for deterministic
    news→symbol linking.
    """
    spec = get_spec(provider_id, path)
    if not spec.enabled:
        raise ValueError(f"provider '{provider_id}' is disabled in the registry")

    if fixture_eod is not None or fixture_index is not None or fixture_news is not None:
        return FixtureProvider(
            provider_id=provider_id,
            eod_bars=fixture_eod or [],
            index_bars=fixture_index or [],
            news_items=fixture_news or [],
        )

    raw = load_registry(path)
    defaults = raw.get("defaults", {}) or {}
    timeout = float(
        http_timeout if http_timeout is not None else defaults.get("timeout_seconds", 30)
    )
    retries = int(max_retries if max_retries is not None else defaults.get("max_retries", 3))
    backoff = float(defaults.get("retry_backoff_seconds", 5))

    news_cfg = spec.endpoints.get("news")
    if news_cfg and news_cfg.get("url"):
        return RssNewsProvider(
            provider_id=provider_id,
            source=spec.id,
            feed_url=str(news_cfg["url"]),
            timeout=timeout,
            max_retries=retries,
            retry_backoff=backoff,
            universe=universe,
            user_agent=str(news_cfg.get("user_agent", DEFAULT_USER_AGENT)),
            transport=transport,
        )

    eod_cfg = spec.endpoints.get("eod")
    if (
        str(eod_cfg.get("client", "") if eod_cfg else "") in ("ssi", "ssi_fastconnect")
        or provider_id in ("ssi_fastconnect", "ssix_finipro")
    ):
        return SSIFastConnectProvider(
            provider_id=provider_id,
            consumer_id=os.getenv("SSI_CONSUMER_ID"),
            consumer_secret=os.getenv("SSI_CONSUMER_SECRET"),
            api_url=str(eod_cfg.get("url", "")) if eod_cfg and eod_cfg.get("url") else None,
            access_token=_credential_value(spec),
            timeout=timeout,
            max_retries=retries,
            retry_backoff=backoff,
            transport=transport,
        )

    if not eod_cfg:
        raise ValueError(
            f"provider '{provider_id}' has no usable 'endpoints.eod' or 'endpoints.news' "
            f"block (status={spec.endpoints_status}); endpoints must be verified (KI-006) "
            "or an offline fixture provider must be used"
        )
    provider_cls: type[HttpJsonProvider] = (
        YahooChartProvider if str(eod_cfg.get("client", "")) == "yahoo_chart" else HttpJsonProvider
    )
    return provider_cls(
        provider_id=provider_id,
        eod_config=dict(eod_cfg),
        timeout=timeout,
        max_retries=retries,
        retry_backoff=backoff,
        credential=_credential_value(spec),
        auth=spec.auth,
        transport=transport,
    )


__all__ = [
    "ProviderSpec",
    "load_registry",
    "provider_specs",
    "get_spec",
    "enabled_by_role",
    "fallback_chain",
    "market_provider_chain",
    "create_provider",
    "DataProvider",
]
