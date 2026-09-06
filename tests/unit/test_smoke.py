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
    from database.seeds.run_all import run_all

    run_all()  # must not raise while scaffold is empty
