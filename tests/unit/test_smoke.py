"""Phase-0 smoke tests: imports, config, CLI wiring.

These run without external services (no DB/Qdrant) so `pytest` succeeds on a
fresh clone as soon as dependencies are installed.
"""

from __future__ import annotations


def test_api_config_loads() -> None:
    from apps.api.config import settings

    assert settings.scoring_version == "baseline_1.0"
    assert settings.llm_provider in {"openai", "anthropic", "local", "mock"}


def test_api_app_imports_and_has_health() -> None:
    from fastapi.testclient import TestClient

    from apps.api.main import app

    with TestClient(app) as client:
        r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_worker_cli_ingest_argument() -> None:
    from apps.worker.cli import main

    assert main(["ingest", "--source", "fixture"]) == 0


def test_seeds_run_all() -> None:
    # Seeds require a live DB (T003+). Verify the wiring imports cleanly here;
    # DB-backed seed behaviour is exercised by the integration tests.
    from database.seeds import seed_exchanges, seed_sectors, seed_vn30  # noqa: F401

    assert seed_exchanges.EXCHANGES  # non-empty
    assert seed_vn30.VN30
