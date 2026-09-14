"""Unit tests for the T002 data-source design (docs/DATA_SOURCES.md).

Validates the machine-readable provider registry `configs/sources.yaml`:
structure, consistency of selection/fallback chains with `providers`, and the
no-secrets policy (credential_env holds env var *names*, never values).

These tests require PyYAML; they are skipped where it is not installed
(adding PyYAML as a project dependency is a separate, explicit decision).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

yaml = pytest.importorskip("yaml")

SOURCES_PATH = Path(__file__).resolve().parents[2] / "configs" / "sources.yaml"

REQUIRED_PROVIDER_FIELDS = {"id", "description", "roles", "auth", "credential_env", "priority"}
VALID_ROLES = {"market", "fundamental", "valuation", "macro", "corporate_events", "news"}
VALID_AUTH = {"none", "query", "bearer"}


@pytest.fixture(scope="module")
def sources() -> dict[str, Any]:
    with SOURCES_PATH.open(encoding="utf-8") as fh:
        return cast(dict[str, Any], yaml.safe_load(fh))


def test_registry_loads_with_expected_sections(sources: dict[str, Any]) -> None:
    for section in ("version", "providers", "selection", "fallback_chains"):
        assert section in sources, f"missing section: {section}"
    assert sources["providers"], "registry must list at least one provider"


def test_providers_have_required_fields(sources: dict[str, Any]) -> None:
    ids = set()
    for provider in sources["providers"]:
        pid = provider.get("id")
        assert pid, "every provider needs an id"
        assert pid not in ids, f"duplicate provider id: {pid}"
        ids.add(pid)
        missing = REQUIRED_PROVIDER_FIELDS - set(provider)
        assert not missing, f"{pid} missing fields: {sorted(missing)}"
        assert provider["roles"], f"{pid} must declare roles"
        assert set(provider["roles"]) <= VALID_ROLES, f"{pid} invalid roles: {provider['roles']}"
        assert provider["auth"] in VALID_AUTH, f"{pid} invalid auth: {provider['auth']}"
        assert isinstance(provider["priority"], int), f"{pid} priority must be int"


def test_primary_market_provider_is_enabled(sources: dict[str, Any]) -> None:
    enabled = [p for p in sources["providers"] if p["enabled"] and "market" in p["roles"]]
    assert enabled, "at least one enabled market provider required"
    best = max(enabled, key=lambda p: p["priority"])
    assert best["id"] == sources["selection"]["market"]


def test_selection_ids_exist_among_providers(sources: dict[str, Any]) -> None:
    ids = {p["id"] for p in sources["providers"]}
    for domain, selected in sources["selection"].items():
        assert selected == "computed" or selected in ids, (
            f"selection.{domain}={selected} not a provider id"
        )


def test_fallback_chains_consistent(sources: dict[str, Any]) -> None:
    ids = {p["id"] for p in sources["providers"]}
    selection = sources["selection"]
    for domain, chain in sources["fallback_chains"].items():
        assert chain, f"fallback chain for {domain} must not be empty"
        unknown = [pid for pid in chain if pid not in ids]
        assert not unknown, f"{domain} chain references unknown providers: {unknown}"
        # The primary for this domain (when not 'computed') must not repeat in its own chain.
        primary = selection.get(domain)
        assert primary not in chain, f"{domain}: primary {primary} duplicated in its fallback chain"
        # Every fallback for a 'computed' domain is meaningless — guard against drift.
        if primary == "computed":
            assert domain == "valuation", f"unexpected computed domain with fallback: {domain}"


def test_no_secret_values_in_registry(sources: dict[str, Any]) -> None:
    """credential_env must hold env var NAMES (or empty string) — never values."""
    forbidden_marker = ("=",)
    for provider in sources["providers"]:
        cred = provider["credential_env"]
        assert isinstance(cred, str), f"{provider['id']} credential_env must be str"
        for marker in forbidden_marker:
            assert marker not in cred, f"{provider['id']} credential_env looks like a value: {cred}"


def test_valuation_has_no_external_source(sources: dict[str, Any]) -> None:
    """Spec §4.2: valuation_daily is computed by the Quant Engine, not ingested."""
    assert sources["selection"]["valuation"] == "computed"
    ids = {p["id"] for p in sources["providers"]}
    for provider in sources["providers"]:
        assert "valuation" not in provider["roles"], (
            f"{provider['id']} claims valuation role — design says computed"
        )
    # silence unused-var lint for ids (kept for readability of the guard above)
    assert ids
