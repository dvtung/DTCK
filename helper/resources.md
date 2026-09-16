# Resources Reference (helpers)

## AI Investment Research & Decision Intelligence Platform

**Last updated:** 2026-09-15

## Technology stack (§34)

| Layer | Tech | Version target |
|---|---|---|
| Language | Python | 3.12/3.13 (Docker); local 3.14 |
| Backend | FastAPI | 0.115+ |
| Database | PostgreSQL + TimescaleDB | timescale/timescaledb:latest-pg16 |
| Vector DB | Qdrant | qdrant/qdrant:latest |
| Data | Pandas / Polars / NumPy | pinned in pyproject |
| ML | scikit-learn, xgboost, lightgbm | Phase 6 |
| Agents | Deterministic orchestrator (T013, no LLM); LangGraph planned (§34) | Phase 5 |
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
| `MARKET_DATA_PROVIDER` / `MARKET_DATA_API_KEY` | market-data provider selector (T002) |
| `FUNDAMENTAL_DATA_PROVIDER` | fundamental provider selector (T002) |
| `NEWS_PROVIDER` / `NEWS_API_KEY` | news provider selector / optional paid key (T002) |
| `FINIPRO_ACCESS_TOKEN` | SSI FiniPro primary provider credential (T002) |
| `VIETSTOCK_API_KEY` | Vietstock VIP data (optional, disabled) |
| `TRADINGECONOMICS_API_KEY` | macro aggregation (optional, disabled) |

## Third-party integrations (T002 — see `configs/sources.yaml`, design in `docs/DATA_SOURCES.md`)

| Name (id) | Purpose | Status |
|---|---|---|
| `ssix_finipro` (SSI FiniPro) | Primary market + fundamental + events + news | **Selected** (T002); endpoints `TO VERIFY` in T004 |
| `vndirect`, `tcbs`, `dsc` | Market/fundamental fallbacks (anonymous, unofficial) | Selected as fallbacks |
| `sbv`, `gso`, `imf_worldbank` | Macro (official public) | Selected |
| `cafef`, `vnexpress`, `vietstock_news` | Vietnamese news (RSS) | Selected |
| `hose`, `hnx`, `vietstock`, `tradingeconomics`, `newsdata` | Official/licensed/paid extras | **Disabled** until licensing/cost decision |

> All credentials masked; never commit real keys. Egress whitelist required for external APIs.

## CLI scripts

- `python -m database.seeds.run_all` — seed reference data
- `python -m apps.worker.cli ingest --source=... --date=...` — run a collector
- `uvicorn apps.api.main:app --reload` — **chạy API REST phát triển** (cổng 8000)
- `python -m apps.api.main` — chạy API bằng `python -m`
- `curl localhost:8000/docs` — tài liệu tương tác (Swagger UI)
- `docker compose exec api alembic upgrade head` — migrate
- `docker compose exec api pytest` — chạy test trong container

## API (T010)

- **Framework:** FastAPI 0.115 · endpoint `/api/v1/*`, tiền tố `docs/api/`.
- **Router:** 7 nhóm (market, stocks, fundamentals, technical, valuation, news, backtests) = 23 đường dẫn · 24 thao tác.
- **Service:** `MarketService` trong bộ nhớ, tất định (7 mã cơ sở, 60 ngày làm việc) — **chưa nối TimescaleDB** (KI-008). Để chuyển: thay `get_market_service()` trong `apps/api/dependencies.py` bằng repository SQLAlchemy.
- **Schemas:** 21 lớp Pydantic trong `apps/api/schemas.py`, gồm `Page[T]` generic + `ErrorResponse`.
- **Kiểm thử:** `pytest tests/unit/test_api.py` — 14 bài (health/readyz, 7 nhóm, phân trang, 404).

## Dependency update protocol

When `pyproject.toml`/`requirements*.txt` change → refresh `offline_package/` wheels and update this file (rule §2.4).

> Note: `PyYAML` was installed into the local venv to verify `tests/unit/test_sources_registry.py`
> (T002) but is **not** yet a project dependency — `pyproject.toml` unchanged. If you approve
> adding `pyyaml` to `[project.optional-dependencies] dev`, registry tests also run in Docker/CI.