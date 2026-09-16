# Memory Bank — Current State

**Last updated:** 2026-09-16

---

## 1. Status per spec §58

```text
Specification:  ████████████████████ 100%   (docs/SYSTEM_SPECIFICATION.md, v1.0)
Architecture:   ████████████████████ 100%   (docs/ARCHITECTURE.md drafted)
Database:       ████████████████████ 100%   (schema + Alembic migration 0001 + seeds DONE)
Data Pipeline:  ████████████████████ 100%   (T004+T005: collectors/validators/normalizers/pipeline + quality framework DONE)
Quant Engine:   ████████████████████ 100%   (T006 indicators + T007 factors/valuation/momentum/risk + T008 scoring engine DONE)
Backtesting:    ██████████████████░░  90%   (T009 engine+metrics+walk-forward DONE; real-market validation pending KI-006/007)
API:            ██████████████████░░  90%   (T010: 7 router groups / 23 paths / 24 ops DONE; T012: +3 ops; T013: +10 ops → 36 paths / 37 ops; DB wiring pending KI-008)
Dashboard:      █████████████████░░░  85%   (T011 Streamlit DONE on synthetic fallback; DB/real-data wiring pending KI-010)
RAG:            █████████████████░░░  85%   (T012 news chunking+embedding+retrieval+rerank+evidence engine DONE; Qdrant adapter best-effort, real news pending KI-006/007)
AI Agent:       ████████████████████  95%
ML:             ████████████████░░░░  80%   (T014: feature dataset + training + calibration + registry + /predictions API DONE; real training pending KI-012)
Production:     ░░░░░░░░░░░░░░░░░░░░   0%
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
- **Data quality framework** (`src/data/quality.py`) — 6-dimension scoring (completeness, validity, consistency, uniqueness, freshness, accuracy) with weighted mean, renormalization, and threshold gate (§39).
- **Scoring engine** (`src/quant/scoring/engine.py`, T008) — `decompose_score()` per-factor contributions with renormalized weights, `score_universe()` → ranked `StockRanking` list, `build_signal_label()` (POSITIVE/NEUTRAL/NEGATIVE), `build_confidence()`; explainability payloads for every ranking.
- **Backtesting engine** (`src/backtesting/`, T009) — `models.py` (PriceBar/BacktestData/ExecutionCosts/Trade/EquityPoint/BacktestConfig/BacktestResult), `metrics.py` (total return, CAGR, volatility, Sharpe, Sortino, max drawdown, Calmar, win rate, profit factor, turnover, transaction-cost total), `engine.py` (`run_backtest`, `select_window`, rebalance/close-leg logic), `walkforward.py` (`walk_forward_windows`, `rolling_windows`). Deterministic, cost-aware, no look-ahead.
- **REST API** (`apps/api/`, T010) — FastAPI app with 7 router groups (`market`, `stocks`, `fundamentals`, `technical`, `valuation`, `news`, `backtests`) = 23 paths / 24 operations per `docs/API_SPECIFICATION.md`; shared pagination + `not_found` error envelope; 21 Pydantic schemas; `/healthz` + `/readyz`; `MarketDep` dependency injection.
- **Streamlit dashboard** (`apps/dashboard/`, T011) — `client.py` (`MarketClient`: HTTP-first over `/api/v1/*`, in-process `MarketService` fallback offline), `components.py` (pure-Python signal/format/ranking/decomposition transforms), `app.py` (6 pages: market overview, screener, rankings, stock detail, backtests, system health; plotly candlestick/scatter/contribution charts).
- Tests: 209 total pass; ruff + mypy (strict over `src/` + `apps/`) clean.
- **Fundamental factors** (`src/market/fundamental/factors.py`) — revenue/EPS growth, ROE, ROA, margins, D/E, interest coverage, FCF, FCF margin, earnings quality. All return `None` on zero denominators.
- **Valuation** (`src/market/valuation/valuation.py`) — P/E, forward P/E, P/B, EV/EBITDA, EV/Sales, dividend yield, PEG, enterprise value + percentile ranks (industry/historical).
- **Momentum** (`src/market/momentum/momentum.py`) — n-day returns, multi-period, volume expansion, relative momentum vs benchmark.
- **Risk** (`src/market/risk/risk.py`) — rolling annualized volatility (log returns), beta, trailing max drawdown, liquidity, gap risk, debt-risk buckets.
- **Factor scoring** (`src/quant/factors/scoring.py`) — §12 baseline weights (fund 0.30/tech 0.20/mom 0.15/val 0.15/qual 0.10/risk 0.10), percentile-rank aggregation, renormalized overall score, stock ranking.
- **Technical indicators** (`src/market/technical/indicators.py`) — SMA, EMA, RSI (Wilder's smoothing), MACD (12/26/9), Bollinger Bands (20, 2σ), ATR (14), OBV, volume SMA, relative strength vs benchmark. Pure-Python, deterministic, tested against hand-computed expected values (40 tests).
- **RAG + evidence engine** (`src/rag/` + `src/evidence/`, T012) — `HashEmbedding` (deterministic hash-based, dim 128, model_name "hash-embed-v1"), `chunk_news_item` (sliding-window chunker w/ metadata + symbol + source + published_at), `MemoryVectorStore` (in-memory cosine store; `upsert`/`query`) + optional `QdrantAdapter` (best-effort mirror when `qdrant_client` importable), `Retriever` (hybrid: vector + keyword overlap + recency + source-reliability priors, metadata filters symbol/doc_type/source), `rerank` (RRF-style re-scoring), `RagService` singleton (`ingest_news_items`/`search`/`evidence_for`/`status`/`to_payload`), `src/evidence/engine.py` (`Evidence` §19 dataclass + `confidence_for` + `build_evidence` + `evidence_to_dict`). 3 new API endpoints (`/api/v1/rag/search`, `/api/v1/rag/status`, `/api/v1/evidence`) → API now 26 paths / 27 ops; `readyz` reports qdrant status ("offline-index-ready" when Qdrant absent).
- Git repo on branch `feat/data-source-design`.

---

## 3. Active Task

**ID:** `T013 — LangGraph agents + orchestrator + audit (Phase 5)`
**State:** COMPLETED (2026-09-15)

**Prior tasks:** `T001 — Phase 0 scaffold` (2026-09-06) · `T003 — migrations+seeds` (2026-09-13) · `T002 — data-source design` (2026-09-13) · `T004+T005 — pipeline+quality` (2026-09-14) · `T006 — technical indicators` (2026-09-14) · `T007 — factors/scoring` (2026-09-14) · `T008+T009+T010 — scoring engine, backtesting engine, FastAPI read API` (2026-09-15) · `T011 — Streamlit dashboard` (2026-09-15)

---

## 4. Blockers / Honors

- Data sources **selected** (T002): SSI FiniPro primary + fallbacks; see `configs/sources.yaml`.
- Provider endpoints/schemas/rate-limits still **unverified** (no network egress in T002) → KI-006, blocks T004 first run.
- No provider credentials yet (`FINIPRO_ACCESS_TOKEN` etc. empty) → KI-007; anonymous fallbacks remain testable.
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
12. ML PREDICTION         → T014 (next)
12. ML PREDICTION         → T014
13. PORTFOLIO INTELLIGENCE
14. PRODUCTION            → T015
```