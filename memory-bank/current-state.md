# Memory Bank — Current State

**Last updated:** 2026-09-25

---

## 1. Status per spec §58

```text
Specification:  ████████████████████ 100%   (docs/SYSTEM_SPECIFICATION.md, v1.0)
Architecture:   ████████████████████ 100%   (docs/ARCHITECTURE.md drafted)
Database:       ████████████████████ 100%   (schema + Alembic migration 0001 + seeds DONE)
Data Pipeline:  ████████████████████ 100%   (T004+T005 DONE + live chain [yahoo,vndirect,tcbs,dsc]; CaféF RSS verified; E2E 62/62 @94.88)
Quant Engine:   ████████████████████ 100%   (T006+T007+T008 DONE + compute-scores job on 4 real symbols)
Backtesting:    ██████████████████░░  90%   (T009 engine+metrics+walk-forward DONE; real validation limited to ~1mo Yahoo history KI-009)
API:            ██████████████████░░  90%   (T010 done; read path on TimescaleDB via MARKET_DATA_SOURCE=db|auto — default still memory; write path open KI-008)
Dashboard:      ███████████████████░  95%   (T011 + live pagination unwrap + Tin tức & RAG page; real data when API serves DB mode)
RAG:            ██████████████████░░  90%   (T012 + 50 real CaféF articles ingested & verified; Qdrant best-effort)
AI Agent:       ████████████████████  95%
ML:             ████████████████░░░░  80%   (T014: feature dataset + training + calibration + registry + /predictions API DONE; real training pending KI-012)
Production:     ███░░░░░░░░░░░░░░░░░  15%   (3-job scheduler + compute-scores DONE 2026-09-25; JWT/RBAC/monitoring/alerts/CI-CD → T015)
```

---

## 2. What Exists Now (Phase-0 scaffold complete + STEP 2 database design implemented)

- **Repo structure** fully scaffolded per spec §35 (`apps/`, `src/`, `database/`, `tests/`, `notebooks/`, `configs/`, `scripts/`, `docs/`, `memory-bank/`, `offline_package/`, `docker/`).
- **Docs set** complete (13+ files, list in `project-context.md` §7).
- **Memory bank** initialized (this set of files).
- `pyproject.toml`, `.env.example`, `.gitignore`, `README.md`, `docker-compose.yml`, Dockerfiles — created.
- **SQLAlchemy models** (`src/common/models/`) implementing every table in `docs/DATABASE_SCHEMA.md` — 38 tables, the single source of truth (`Base.metadata`).
- **Alembic migration** `database/migrations/versions/0001_initial_schema.py` → creates all tables + converts 12 time-series tables into TimescaleDB hypertables (per §17), with `upgrade`/`downgrade`. Verified up → down → up against the live Docker TimescaleDB.
- **Seeds** (`database/seeds/`) — exchanges (HOSE/HNX/UPCOM), 10 sectors + 15 industries, 30-row VN30 universe. Idempotent; wired into `database/seeds/run_all.py`.
- **Data pipeline** (`src/data/`) — collectors, validators, normalizers, pipelines, providers (base + fixture + HTTP-JSON + registry), quality scoring (§39). FixtureProvider enables full offline pipeline testing. Worker CLI (`apps/worker/cli.py`) wired for ingest commands.
- **Real-data milestone (2026-09-24/25)** — `YahooChartProvider` (public VN EOD, priority 85, `VERIFIED_2026-09-25`; chain `[yahoo,vndirect,tcbs,dsc]`; split un-adjust via `events=split`; un-adjusted closes) + `RssNewsProvider` for CaféF (`VERIFIED_2026-09-25`; 50 real articles ingested, multi-symbol chunk linking). Live `ingest --source yahoo --symbols FPT,VCB,HPG,ACB` → **fetched=62 written=62 issues=0 quality=94.88** (gate passed); `compute-scores --lookback 60` → scored=4 real symbols into `factor_scores`.
- **DB read path (W1, 2026-09-25)** — `MarketSource` protocol + `DbMarketService` (13 real table groups, per-request cache) behind `MARKET_DATA_SOURCE=memory|db|auto` (`apps/api/dependencies.py`); routers untouched, `/readyz` reports `"source"`. Compose api/worker default to `auto`; code + `.env.example` default stays `memory` so unit tests need no DB.
- **Worker scheduler (Option 2, 2026-09-24)** — APScheduler 3 jobs (`run_scheduler`): news every N minutes (CaféF), EOD Mon–Fri 15:05 ICT (Yahoo), scoring Mon–Fri 15:30 ICT (`compute-scores` in-process); fail-soft, `max_instances=1` + `coalesce`, `SCHEDULER_JOBS_ENABLED=false` disables. `SCHEDULER_*` names match `Settings` ↔ `.env.example` ↔ `docker-compose.yml`.
- **Dashboard live wiring (Option 1, 2026-09-24)** — client unwraps `{items}` pagination envelopes, `search_rag`/`get_rag_status`/`get_evidence` added; new "Tin tức & RAG" page; `evidence_rows`/`rag_doc_rows` helpers.
- **Data quality framework** (`src/data/quality.py`) — 6-dimension scoring (completeness, validity, consistency, uniqueness, freshness, accuracy) with weighted mean, renormalization, and threshold gate (§39).
- **Scoring engine** (`src/quant/scoring/engine.py`, T008) — `decompose_score()` per-factor contributions with renormalized weights, `score_universe()` → ranked `StockRanking` list, `build_signal_label()` (POSITIVE/NEUTRAL/NEGATIVE), `build_confidence()`; explainability payloads for every ranking.
- **Backtesting engine** (`src/backtesting/`, T009) — `models.py` (PriceBar/BacktestData/ExecutionCosts/Trade/EquityPoint/BacktestConfig/BacktestResult), `metrics.py` (total return, CAGR, volatility, Sharpe, Sortino, max drawdown, Calmar, win rate, profit factor, turnover, transaction-cost total), `engine.py` (`run_backtest`, `select_window`, rebalance/close-leg logic), `walkforward.py` (`walk_forward_windows`, `rolling_windows`). Deterministic, cost-aware, no look-ahead.
- **REST API** (`apps/api/`, T010; **38 paths / 39 operations** on `/api/v1/*` per `docs/api.html`, 2026-09-25: 12 router files × 40 ops incl. `POST /backtests`, excluding `/healthz`+`/readyz`+`/docs`+`/redoc`; earlier labels "14 nhóm" counted tags loosely) — FastAPI app with router groups (`market`, `stocks`, `fundamentals`, `technical`, `valuation`, `news`, `backtests`, `rag`+`evidence`, `agents`+`analysis`, `auth`, `monitoring`, `predictions`) per `docs/API_SPECIFICATION.md`; shared pagination + `not_found` error envelope; 21 Pydantic schemas; `/healthz` + `/readyz` (reports market-data `"source"`); `MarketDep` dependency injection resolving `MarketSource` (memory vs `DbMarketService`).
- **Streamlit dashboard** (`apps/dashboard/`, T011) — `client.py` (`MarketClient`: HTTP-first over `/api/v1/*`, unwraps `{items}` pagination envelopes, RAG/evidence methods, in-process `MarketService` fallback offline), `components.py` (pure-Python signal/format/ranking/decomposition transforms + `evidence_rows`/`rag_doc_rows`), `app.py` (7 pages: market overview, screener, rankings, stock detail, backtests, system health, Tin tức & RAG; plotly candlestick/scatter/contribution charts).
- Tests: **422 passed, 3 skipped** (2026-09-25: `LLM_PROVIDER=mock pytest`); ruff + mypy (126 files) clean. Known unrelated failure: `test_smoke::test_api_config_loads` rejects a local `.env` with `LLM_PROVIDER=ollama`.
- **Fundamental factors** (`src/market/fundamental/factors.py`) — revenue/EPS growth, ROE, ROA, margins, D/E, interest coverage, FCF, FCF margin, earnings quality. All return `None` on zero denominators.
- **Valuation** (`src/market/valuation/valuation.py`) — P/E, forward P/E, P/B, EV/EBITDA, EV/Sales, dividend yield, PEG, enterprise value + percentile ranks (industry/historical).
- **Momentum** (`src/market/momentum/momentum.py`) — n-day returns, multi-period, volume expansion, relative momentum vs benchmark.
- **Risk** (`src/market/risk/risk.py`) — rolling annualized volatility (log returns), beta, trailing max drawdown, liquidity, gap risk, debt-risk buckets.
- **Factor scoring** (`src/quant/factors/scoring.py`) — §12 baseline weights (fund 0.30/tech 0.20/mom 0.15/val 0.15/qual 0.10/risk 0.10), percentile-rank aggregation, renormalized overall score, stock ranking.
- **Technical indicators** (`src/market/technical/indicators.py`) — SMA, EMA, RSI (Wilder's smoothing), MACD (12/26/9), Bollinger Bands (20, 2σ), ATR (14), OBV, volume SMA, relative strength vs benchmark. Pure-Python, deterministic, tested against hand-computed expected values (40 tests).
- **RAG + evidence engine** (`src/rag/` + `src/evidence/`, T012) — `HashEmbedding` (deterministic hash-based, dim 128, model_name "hash-embed-v1"), `chunk_news_item` (sliding-window chunker w/ metadata + symbol + source + published_at), `MemoryVectorStore` (in-memory cosine store; `upsert`/`query`) + optional `QdrantAdapter` (best-effort mirror when `qdrant_client` importable), `Retriever` (hybrid: vector + keyword overlap + recency + source-reliability priors, metadata filters symbol/doc_type/source), `rerank` (RRF-style re-scoring), `RagService` singleton (`ingest_news_items`/`search`/`evidence_for`/`status`/`to_payload`), `src/evidence/engine.py` (`Evidence` §19 dataclass + `confidence_for` + `build_evidence` + `evidence_to_dict`). 3 new API endpoints (`/api/v1/rag/search`, `/api/v1/rag/status`, `/api/v1/evidence`) → API now 26 paths / 27 ops at T012; grown since to **38 paths / 39 operations** (2026-09-25: 12 router files × 40 ops incl. `POST /backtests`). `readyz` reports qdrant status ("offline-index-ready" when Qdrant absent). **2026-09-24/25:** 50 real CaféF articles ingested into the index (multi-symbol chunk linking); `/rag/search` + `/evidence` verified live; dashboard Tin tức & RAG page + `evidence_rows`/`rag_doc_rows` helpers.
- Git repo on branch `feat/data-source-design`.

---

## 3. Active Task

**ID:** `D3 — Static docs relocation + live-data refresh + env wiring (2026-09-25)`
**State:** COMPLETED

**Verification:** `LLM_PROVIDER=mock pytest` → 422 passed, 3 skipped · `ruff check .` clean · `mypy` clean (126 files) · 7 HTML pages tag-balanced · internal link check OK (`style.css` + cross-links resolve).

**Deliverables so far (2026-09-25):**
- Vietnamese HTML site moved `docs/htmldocs/` → `docs/` (staged `git mv` renames, history preserved); `style.css` links stay relative (`href="style.css"`), all pages cross-link with flat relative hrefs.
- `status.html` refreshed: E2E ingest row (62/62 @94.88), env-config section (`MARKET_DATA_SOURCE`, `SCHEDULER_*`, RAG, quality gate, source settings), KI-006/KI-008/KI-010/KI-011 partial status, 38 paths / 39 ops, 422 tests; Romanian-mixed text in `modules.html` fixed (`rag_doc_rows`).
- `.env.example` + `docker-compose.yml`: `MARKET_DATA_SOURCE` (compose `:-auto`, code default `memory`) and all 10 `SCHEDULER_*` names match `Settings` fields in `apps/api/config.py` (pydantic-settings `SCHEDULER_` prefix mapping verified).

**Still to do:** memory-bank close-out (this file, changelog) → final validation (HTML links, `LLM_PROVIDER=mock pytest`, ruff, mypy) → cleanup → commit.

**Prior tasks:** `T001 — Phase 0 scaffold` (2026-09-06) · `T003 — migrations+seeds` (2026-09-13) · `T002 — data-source design` (2026-09-13) · `T004+T005 — pipeline+quality` (2026-09-14) · `T006 — technical indicators` (2026-09-14) · `T007 — factors/scoring` (2026-09-14) · `T008+T009+T010 — scoring engine, backtesting engine, FastAPI read API` (2026-09-15) · `T011 — Streamlit dashboard` (2026-09-15) · `T013 — agents` (2026-09-15) · `T014 — ML` (2026-09-16) · `W1/W1b/W2 + Options 1–3 — real-data milestone E2E` (2026-09-24/25, above)

---

## 4. Blockers / Honors

- Data sources **selected** (T002) + **live chain verified** (2026-09-25): Yahoo chart EOD + CaféF RSS carry ingestion (`VERIFIED_2026-09-25` in `configs/sources.yaml`); SSIX/VNDirect/TCBS/DSC/WSJ still pending network/keys → KI-006/KI-007 partially open.
- API read path on TimescaleDB (`MARKET_DATA_SOURCE=db|auto` → KI-008 partial); default stays `memory`; API has no write path; compose api/worker default to `auto` (needs image rebuild: `docker compose build api worker` + recreate).
- Docker services are started & healthy (db, qdrant, api, worker, dashboard); DB migration + seeds verified against the running TimescaleDB.
- Local Python is 3.14; DB deps (SQLAlchemy 2.0.52, Alembic 1.20, psycopg 3.3) install & work locally. Docker images use Python 3.12.

---

## 5. Next Steps (ordered by spec §57)

```text
1. DATABASE DESIGN        → DONE (schema + migration 0001 + seeds, 2026-09-13)
2. REPOSITORY STRUCTURE   → done (scaffold)
3. DATA SOURCE DESIGN     → DONE (docs/DATA_SOURCES.md + configs/sources.yaml, 2026-09-13)
4. DATA INGESTION         → DONE (T004: collectors/validators/normalizers/pipeline, 2026-09-14)
5. DATA QUALITY           → DONE (T005: 6-dimension scoring + gate, 2026-09-14)
6. QUANT ENGINE           → DONE (T006 indicators · T007 factors · T008 scoring engine)
7. BACKTEST ENGINE        → DONE (T009 engine + metrics + walk-forward, 2026-09-15)
8. API LAYER              → DONE (T010 FastAPI /api/v1/*, 2026-09-15)
9. DASHBOARD              → DONE (T011 Streamlit overview/screener/rankings/detail/backtests/health, 2026-09-15)
10. RAG                   → DONE (T012 news+RAG+evidence, 2026-09-15; Qdrant adapter best-effort — KI-011)
11. AI AGENT              → DONE (T013, 2026-09-16: 4 agents + orchestrator + audit + 70 tests)
12. ML PREDICTION         → DONE (T014, 2026-09-16; real training pending KI-012)
12b. CODE AUDIT           → DONE (MAINT-2026-09-17: 16 logic/consistency fixes, 342 tests)
12c. REAL-DATA MILESTONE    → DONE (2026-09-24/25: dashboard live wiring + 3-job scheduler + Yahoo/CaféF verified + DB read path + compute-scores; E2E 62/62 @94.88; 422 tests)
12d. DOCS RELOCATION        → DONE (2026-09-25: docs/htmldocs/ → docs/ + live-data refresh + env wiring; 422 tests · ruff · mypy · HTML validated)
13. PORTFOLIO INTELLIGENCE
14. PRODUCTION            → T015
```