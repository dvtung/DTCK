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

API/worker Docker images install `.[dev,ml]`: scikit-learn `>=1.4,<2.0`,
xgboost `>=2.0,<3.0`, lightgbm `>=4.3,<5.0` (declared in `pyproject.toml`).
Rebuild after Dockerfile dependency changes; restarting does not update packages.
See the sklearn troubleshooting steps in `helper/deployment.md`.


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
| `MARKET_DATA_SOURCE` | API read path: `memory` (default, no DB) / `db` (TimescaleDB) / `auto` (DB when `prices` non-empty, else memory); compose defaults to `auto` |
| `SCHEDULER_JOBS_ENABLED` | `true` = run news/EOD/scoring jobs; `false` = scheduler off, `/news/ingest` still available |
| `SCHEDULER_NEWS_SOURCE` / `SCHEDULER_NEWS_INTERVAL_MINUTES` | news provider (default `cafef`) + poll interval (default `15` min) |
| `SCHEDULER_EOD_SOURCE` / `SCHEDULER_EOD_CRON_HOUR` / `SCHEDULER_EOD_CRON_MINUTE` / `SCHEDULER_EOD_LOOKBACK_DAYS` | EOD source (`yahoo`) · Mon–Fri 15:05 ICT (`15`/`5`) · idempotent re-fetch window (`7` days) |
| `SCHEDULER_SCORING_CRON_HOUR` / `SCHEDULER_SCORING_CRON_MINUTE` | scoring job Mon–Fri 15:30 ICT (`15`/`30`), after the EOD job |
| `DATA_QUALITY_THRESHOLD` | quality gate 0–100 (`80.0`); batches below are `below_threshold` and unused downstream |

## Third-party integrations (T002 — see `configs/sources.yaml`, design in `docs/DATA_SOURCES.md`)

| Name (id) | Purpose | Status |
|---|---|---|
| `ssix_finipro` (SSI FiniPro) | Primary market + fundamental + events + news | **Selected** (T002); endpoints `TO VERIFY` in T004 |
| `yahoo` | Market fallback — EOD OHLCV for `.VN` tickers (anonymous) | **Verified 2026-09-25**; split un-adjustment + placeholder-row rules in `YahooChartProvider` |
| `vndirect`, `tcbs`, `dsc` | Market/fundamental fallbacks (anonymous, unofficial) | Selected as fallbacks (vndirect/tcbs unreachable from host 2026-09-25) |
| `sbv`, `gso`, `imf_worldbank` | Macro (official public) | Selected |
| `cafef`, `vnexpress`, `vietstock_news` | Vietnamese news (RSS) | CaféF **verified 2026-09-25** (`RssNewsProvider` stdlib parse; 50 real articles ingested); others selected |
| `hose`, `hnx`, `vietstock`, `tradingeconomics`, `newsdata` | Official/licensed/paid extras | **Disabled** until licensing/cost decision |

> All credentials masked; never commit real keys. Egress whitelist required for external APIs.

## CLI scripts

- `python -m database.seeds.run_all` — seed reference data
- `python -m apps.worker.cli ingest --dataset prices --source fixture --symbols FPT,VCB --start … --end …` — run a collector
  (`--dataset prices` requires `--symbols`; exits `2` instead of reporting an empty ingest as success)
- `python -m apps.worker.cli ingest --dataset prices --source yahoo --symbols FPT,VCB,HPG,ACB --start 2026-09-01 --end 2026-09-25` — live VN EOD (verified 2026-09-25: fetched=62 written=62 quality=94.88)
- `python -m apps.worker.cli compute-scores [--lookback 60]` — recompute price-derived factors into `factor_scores`
- `python -m apps.worker.main scheduler` — start the APScheduler loop (news / EOD / scoring); `SCHEDULER_JOBS_ENABLED=false` disables jobs
- `python -m apps.worker.cli train-model [--horizon 5] [--algorithm xgboost|lightgbm]` — train + calibrate + register
  (`lightgbm` needs the optional `[ml]` extra; the CLI reports honestly when it is missing)
- `python -m apps.worker.cli run-agent --task analyze --symbol FPT` — offline agent run
- `uvicorn apps.api.main:app --reload` — **chạy API REST phát triển** (cổng 8000)
- `python -m apps.api.main` — chạy API bằng `python -m`
- `curl localhost:8000/docs` — tài liệu tương tác (Swagger UI)
- `docker compose exec api alembic upgrade head` — migrate
- `docker compose exec api pytest` — chạy test trong container

## API (T010; 38 paths / 39 ops per `docs/api.html`, 2026-09-25)

- **Framework:** FastAPI 0.115 · endpoint `/api/v1/*`, tiền tố `docs/api/`.
- **Router:** nhóm market, stocks, fundamentals, technical, valuation, news, rag, evidence, backtests, predictions, agents.
- **Service:** `MarketSource` protocol (`apps/api/services/market_source.py`) — `MarketService` trong bộ nhớ, tất định (mặc định; KI-008 phần đọc đã mở) hoặc `DbMarketService` đọc TimescaleDB khi `MARKET_DATA_SOURCE=db|auto`; `/readyz` báo `"source"`. Để mở rộng: nối repository SQLAlchemy mới vào `DbMarketService`, không đụng router.
- **Schemas:** 21 lớp Pydantic trong `apps/api/schemas.py`, gồm `Page[T]` generic + `ErrorResponse`.
- **Kiểm thử:** `pytest tests/unit/test_api.py` (health/readyz, nhóm router, phân trang, 404) + `tests/unit/test_market_data_source.py` + integration `tests/integration/test_db_market.py`.

## Dependency update protocol

When `pyproject.toml`/`requirements*.txt` change → refresh `offline_package/` wheels and update this file (rule §2.4).

> Note: `PyYAML` was installed into the local venv to verify `tests/unit/test_sources_registry.py`
> (T002) but is **not** yet a project dependency — `pyproject.toml` unchanged. If you approve
> adding `pyyaml` to `[project.optional-dependencies] dev`, registry tests also run in Docker/CI.