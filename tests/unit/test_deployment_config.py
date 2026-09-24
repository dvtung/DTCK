"""Deployment configuration contracts: Alembic ↔ Docker images (docs/DEPLOYMENT_vi.md).

`alembic upgrade head` runs inside the containers from the image WORKDIR, so the
repo-root ``alembic.ini`` (``script_location = database/migrations``) has to be
present there next to the migration scripts. These tests pin that invariant —
without it, ``docker compose exec api alembic upgrade head`` fails with
``FAILED: No 'script_location' key found in configuration``.
"""

from __future__ import annotations

import configparser
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"
DOCKER_DIR = REPO_ROOT / "docker"
DOCKERFILES = ("Dockerfile.api", "Dockerfile.worker", "Dockerfile.dashboard")
IMAGE_WORKDIR = "WORKDIR /app"


def _dockerfile(name: str) -> str:
    return (DOCKER_DIR / name).read_text(encoding="utf-8")


def test_alembic_ini_points_at_existing_migration_scripts() -> None:
    parser = configparser.ConfigParser()
    assert parser.read(ALEMBIC_INI, encoding="utf-8"), f"cannot read {ALEMBIC_INI}"

    script_location = parser.get("alembic", "script_location")
    # Relative on purpose: it is resolved against the image WORKDIR (/app).
    assert not Path(script_location).is_absolute()
    scripts = REPO_ROOT / script_location
    assert (scripts / "env.py").is_file()
    assert list((scripts / "versions").glob("*.py")), "no revision modules found"


def test_alembic_ini_holds_no_real_credentials() -> None:
    parser = configparser.ConfigParser()
    parser.read(ALEMBIC_INI, encoding="utf-8")
    url = parser.get("alembic", "sqlalchemy.url")
    assert url.startswith("postgresql+psycopg://")
    assert "change_me" in url  # placeholder; env.py prefers DATABASE_URL at runtime

    env_py = (REPO_ROOT / "database" / "migrations" / "env.py").read_text(encoding="utf-8")
    assert 'os.getenv("DATABASE_URL"' in env_py


@pytest.mark.parametrize("dockerfile_name", DOCKERFILES)
def test_alembic_config_ships_with_the_migration_scripts(dockerfile_name: str) -> None:
    content = _dockerfile(dockerfile_name)
    assert IMAGE_WORKDIR in content, f"{dockerfile_name} must run from /app"
    carries_migrations = "COPY database ./database" in content
    carries_config = "alembic.ini" in content
    assert carries_config == carries_migrations, (
        f"{dockerfile_name}: alembic.ini and database/ must ship together — "
        "script_location is resolved relative to the image WORKDIR"
    )


def test_documented_migration_runner_image_can_run_alembic() -> None:
    """docs/DEPLOYMENT_vi.md runs migrations via `docker compose exec api alembic ...`."""
    api_dockerfile = _dockerfile("Dockerfile.api")
    assert "alembic.ini" in api_dockerfile
    assert "COPY database ./database" in api_dockerfile


def test_alembic_cli_is_a_core_dependency() -> None:
    """The CLI must be installed by every image (not hidden behind an extra)."""
    core_dependencies = (
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        .split("[project.optional-dependencies]", 1)[0]
    )
    assert "alembic>" in core_dependencies
