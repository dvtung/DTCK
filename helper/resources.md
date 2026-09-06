# Resources Reference (helpers)

## AI Investment Research & Decision Intelligence Platform

**Last updated:** 2026-09-06

## Technology stack (§34)

| Layer | Tech | Version target |
|---|---|---|
| Language | Python | 3.12/3.13 (Docker); local 3.14 |
| Backend | FastAPI | 0.115+ |
| Database | PostgreSQL + TimescaleDB | timescale/timescaledb:latest-pg16 |
| Vector DB | Qdrant | qdrant/qdrant:latest |
| Data | Pandas / Polars / NumPy | pinned in pyproject |
| ML | scikit-learn, xgboost, lightgbm | Phase 6 |
| Agents | LangGraph | Phase 5 |
| Dashboard | Streamlit | 1.3x |
| Migrations | Alembic + SQLAlchemy | 2.x |

## Environment variables (from `.env.example`)

| Var | Purpose |
|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | DB credentials |
| `DATABASE_URL` | SQLAlchemy DSN |
| `QDRANT_URL` | Qdrant endpoint |
| `LLM_PROVIDER` / `LLM_API_KEY` / `LLM_MODEL` | LLM abstraction (ADR-005) |
| `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` | embedding service (Phase 4) |
| `LOG_LEVEL` | logging severity |

## Third-party integrations

| Name | Purpose | Status |
|---|---|---|
| TBD — Vietnam market data provider (OHLCV/foreign flow) | Phase 1 collector | **Not selected yet (KI-001)** |
| TBD — financial statements provider | Phase 1 | Not selected |
| TBD — news provider | Phase 4 | Not selected |

> All credentials masked; never commit real keys. Egress whitelist required for external APIs.

## CLI scripts

- `python -m database.seeds.run_all` — seed reference data
- `python -m apps.worker.cli ingest --source=... --date=...` — run a collector
- `docker compose exec api alembic upgrade head` — migrate

## Dependency update protocol

When `pyproject.toml`/`requirements*.txt` change → refresh `offline_package/` wheels and update this file (rule §2.4).