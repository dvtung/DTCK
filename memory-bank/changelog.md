# Memory Bank — Changelog

**Last updated:** 2026-09-06

## 2026-09-06 — Phase 0 complete (+ verification)

- Initialized git repository (`/home/dvtung/Projects/DTCK`).
- Scaffolded repo layout per spec §35.
- Moved/copied spec files into `docs/`:
  - `docs/SYSTEM_SPECIFICATION.md` (canonical, v1.0, 58 sections)
  - `docs/AI_INVESTMENT_CONCEPT.md` (earlier concept draft)
- Authored docs set (13 files): ARCHITECTURE, DATABASE_SCHEMA, DATA_ARCHITECTURE, QUANT_ENGINE, BACKTESTING, ML_ARCHITECTURE, RAG_ARCHITECTURE, AGENT_ARCHITECTURE, API_SPECIFICATION, DEPLOYMENT, SECURITY + the two spec files.
- Initialized memory bank: project-context, current-state, decisions, architecture-decisions, known-issues, tasks, changelog.
- Created: `pyproject.toml`, `.env.example`, `.gitignore`, `README.md`, `requirements.txt`, `docker-compose.yml`, `docker/Dockerfile.api`, `docker/Dockerfile.worker`, `docker/Dockerfile.dashboard`.
- Added app entry points: `apps/api/main.py` (+`config.py`), `apps/worker/main.py` (+`cli.py`), `apps/dashboard/app.py`.
- Added Alembic skeleton (`alembic.ini`, `database/migrations/env.py`, `script.py.mako`) and `database/seeds/run_all.py`.
- Added package placeholder `__init__.py` (49 files) under `src/`, `apps/`, `database/`, `tests/`.
- Added `helper/deployment.md` and `helper/resources.md` (operational guides per engineering rules), `offline_package/` (README + requirements-offline.txt), `configs/scoring_weights.yaml`, `scripts/README.md`, `notebooks/README.md`.
- Added smoke test `tests/unit/test_smoke.py`.
- **Verified:** `docker compose config` OK · `pyproject.toml` parses · `python -m py_compile` OK · `ruff check` clean · `pytest` → **4 passed** (local venv `.venv`, Python 3.14).
- No application code written yet (by design — Phase 1 is data foundation).