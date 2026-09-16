# Memory Bank — Changelog

**Last updated:** 2026-09-16

## 2026-09-16 — T014: ML prediction (feature dataset + training + calibration + registry + API)

- Completed `src/ml/` (T014):
  - `feature_dataset.py` — `FeatureDatasetBuilder` with strict as-of alignment; **removed target leakage** (`horizon_return_*` forward returns had been written into the feature matrix — `horizon_return_5d` equaled the training target); process-stable `zlib.crc32` symbol encoding (was `hash()`, PYTHONHASHSEED-randomized); `MarketLike` Protocol typed against `MarketService`
  - `training.py` — `ModelTrainer`: temporal 60/20/20 split on **unique trade dates** (row-count split could place one date in two partitions), XGBoost fit, **custom `_SigmoidCalibrator`** (replaces `CalibratedClassifierCV cv="prefit"`, removed in scikit-learn 1.8), classification metrics (AUC/Brier/log-loss/accuracy/precision/recall/F1), input validation (row alignment, 0/1 labels, ≥3 dates) and **single-class partition guards** — `train_and_register()` → APPROVED entry
  - `model_registry.py` / `predictor.py` — lifecycle EXPERIMENTAL→…→DEPRECATED + prediction service with deterministic fallback stub
- Added `apps/api/routers/predictions.py` — 3 endpoints: `GET /api/v1/predictions/{symbol}`, `/predictions/{symbol}/evaluations`, `/predictions/{symbol}/validation` (spec §2.8) → API 39 paths / 40 ops
- Added `apps/worker/cli.py` `train-model` command (+ `build_parser()` refactor); on the synthetic fixture it fails loudly (single-class labels) instead of registering a fake model
- Added tests: `test_ml_no_leakage.py` (5: no forward-return columns, future-shock invariance, target reacts to future prices, PYTHONHASHSEED stability), `test_ml_training.py` (7: real fit/calibration, date-partition sizes, per-partition single-class rejection, target/label/alignment validation), +5 predictions API tests +2 CLI tests in `test_t014_t015.py`
- Added **KI-012**: synthetic fixture is monotonically rising → 100% positive 5-day labels; real classifier training impossible until real data loads (blocked by KI-006/007/008); predictor serves deterministic fallback meanwhile
- Updated `docs/htmldocs/status.html` (ML 80% · T014 row · KI-012 · roadmap → T015); memory-bank (active-task/current-state/current tasks)
- Verified: **325 total tests pass** · `ruff check .` clean · `mypy` → "Success: no issues found in 119 source files"

## 2026-09-15 — T012: News ingestion + RAG + evidence engine (Phase 4 → MVP-2)

- Added `src/rag/` (T012):
  - `embedding/hash_embed.py` — `HashEmbedding`: deterministic hash-based embedding (dim 128, `model_name="hash-embed-v1"`), no external model dep; `embed(text) -> list[float]`
  - `ingestion/chunking.py` — `Chunk` dataclass + `chunk_news_item(item, max_chars=800)`: sliding-window chunker with metadata (symbol, doc_type="news", source, published_at, title)
  - `retrieval/store.py` — `MemoryVectorStore` (in-memory cosine store, `upsert`/`query`/`size`) + `QdrantAdapter` (best-effort mirror, importable `qdrant_client` only)
  - `retrieval/retriever.py` — `RankedDoc` + `Retriever.retrieve(...)`: hybrid vector + keyword overlap + recency + source-reliability priors, metadata filters (symbol/doc_type/source)
  - `reranking/reranker.py` — `rerank(query, docs)`: RRF-style re-scoring combining vector/keyword/recency ranks
  - `service.py` — `RagService`: singleton `ingest_news_items`/`search`/`evidence_for`/`status`/`to_payload`/`evidence_payload`
- Added `src/evidence/engine.py` — `Evidence` (§19) dataclass + `confidence_for(doc)` + `build_evidence(...)` + `evidence_to_dict(ev)`; fine-grained provenance (chunk id, symbol, source, published_at, snippet)
- Added API wiring:
  - `apps/api/routers/rag.py` — 3 endpoints: `GET /api/v1/rag/search`, `GET /api/v1/rag/status`, `GET /api/v1/evidence` → API total **26 paths / 27 ops** (was 23/24)
  - `apps/api/services/rag_service.py` — `get_rag_service()` process-wide singleton, lazily seeded from `MarketService().list_news()` fixture (KI-011)
  - `apps/api/main.py` — `rag` router registered; `readyz` now reports `qdrant` status (`offline-index-ready` when client absent)
- Added `tests/unit/test_rag_evidence.py` (20 tests: chunking, embedding stability/determinism, store upsert/query, hybrid retrieval filters, rerank monotonicity, evidence confidence ranges, evidence dict schema) + 3 new API tests in `tests/unit/test_api.py`
- Added KI-011 (RAG index over synthetic news; Qdrant adapter best-effort; real news blocked by KI-006/KI-007)
- Updated `docs/htmldocs/` (standing rule): `status.html` RAG bar 0→85% + T012 row + roadmap (T013 next) + KI-011 row; `index.html` RAG rows + 232 test badge; `modules.html` T012 RAG section + TOC anchor; `api.html` rag/evidence endpoints + 26/27 counts; `structure.html` rag/evidence marked done
- Verified: **232 total tests pass** · `ruff check .` clean · `mypy src/ apps/` → "Success: no issues found in 102 source files"

## 2026-09-15 — T011: Streamlit dashboard

- Added `apps/dashboard/` (T011):
  - `client.py` — `MarketClient`: HTTP-first over `/api/v1/*`, in-process `MarketService` fallback offline; methods for indices/regime/breadth, stocks/ranked/prices/ranking, indicators, valuation, quality, news, backtests/backtest/metrics/trades, health; `API_HOST` env overrides default
  - `components.py` — framework-agnostic formatting/transforms: `signal_label/signal_color`, `format_price/format_percent/format_date`, `ranking_rows/contribution_rows/price_dataframe/indicator_dict/quality_bar_labels/metric_rows/news_rows`
  - `app.py` — 6 Streamlit pages: market overview, screener, rankings, stock detail, backtests, system health (plotly candlestick/scatter/contribution charts)
  - Added `tests/unit/test_dashboard.py` (34 tests); added `plotly` to `pyproject.toml` deps + mypy overrides for UI libs
  - Added KI-010 (dashboard serves synthetic in-memory data until TimescaleDB + real data wired)
  - Updated `docs/htmldocs/`: dashboard row DONE in `status.html` + completed-tasks table + KI table, dashboard row in `index.html` platform section, T011 dashboard section + TOC anchor in `modules.html`
- Verified: **209 total tests pass** · `ruff check .` clean · `mypy src/ apps/` → "Success: no issues found in 93 source files"

## 2026-09-15 — T008/T009/T010: explainability, backtesting, API layer

- Added `src/quant/scoring/engine.py` (T008):
  - `decompose_score(factor_scores, weights=None)` — per-factor contributions with renormalized weights (missing/zero handled)
  - `score_universe(universe_scores, weights=None)` → ranked `StockRanking` list
  - `build_signal_label(score)` → POSITIVE/NEUTRAL/NEGATIVE (§44)
  - `build_confidence(overall, n_factors)` — confidence decays as factors drop out
  - Dataclasses: `FactorContribution`, `ScoreDecomposition`, `StockRanking`
  - Added `tests/unit/test_scoring_engine.py` (11 tests)
- Added `src/backtesting/` (T009):
  - `models.py` — `PriceBar`, `BacktestData`, `ExecutionCosts`, `Trade`, `EquityPoint`, `BacktestConfig`, `BacktestResult`
  - `metrics.py` — 11 metrics: `total_return`, `cagr`, `annualized_volatility`, `sharpe_ratio`, `sortino_ratio`, `max_drawdown`, `calmar_ratio`, `win_rate`, `profit_factor`, `turnover`, `transaction_cost_total`, + `compute_metrics`
  - `engine.py` — `run_backtest` (next-bar-open fills, cost-aware), `select_window`
  - `walkforward.py` — `walk_forward_windows`, `rolling_windows`, `WalkForwardWindow`
  - Added `tests/unit/test_backtesting.py` (10 tests)
- Added `apps/api/` (T010):
  - `main.py` — FastAPI app, `/healthz`, `/readyz`
  - 7 routers: `market`, `stocks`, `fundamentals`, `technical`, `valuation`, `news`, `backtests` = 23 paths / 24 operations
  - `schemas.py` (21 Pydantic models incl. generic `Page[T]`, `ErrorResponse`)
  - `dependencies.py` (`MarketDep`), `services/market_data.py` (in-memory deterministic service — KI-008)
  - `routers/common.py` — `paginate_params`, `page_of`, `not_found` envelope
  - Added `tests/unit/test_api.py` (14 tests)
  - Documented new T008/T009/T010 module sections in `docs/htmldocs/modules.html`
  - Created `docs/htmldocs/api.html` — reference page for the REST API
  - Updated `docs/htmldocs/status.html` and `structure.html`
- Verified: **175 total tests pass** · `ruff check .` clean · `mypy src/ apps/` → "Success: no issues found in 91 source files"
- Added `KI-008` (API uses in-memory synthetic service, not wired to TimescaleDB yet) and `KI-009` (backtest validated on synthetic data only) to `known-issues.md`


- New standing rule (recorded in `tasks.md` + `decisions.md`): every future task
  that changes source code, schema, configs, or behavior MUST also update
  `docs/htmldocs/` (Vietnamese) in the same task — status page, module
  reference, and any other affected page — and re-validate the HTML before
  marking the task complete. Prevents docs drift as the project evolves.

## 2026-09-14 — T007 Quant Engine: factors/valuation/momentum/risk + scoring (Phase 2)

- Added `src/market/fundamental/factors.py` — revenue/EPS growth, ROE, ROA, gross/operating/net margins, D/E, interest coverage, FCF, FCF margin, earnings quality (`None` on zero denominators)
- Added `src/market/valuation/valuation.py` — P/E, forward P/E, P/B, EV/EBITDA, EV/Sales, dividend yield, PEG, enterprise value + percentile/industry/historical percentile ranks
- Added `src/market/momentum/momentum.py` — n-day returns, multi-period returns, volume expansion, relative momentum vs benchmark
- Added `src/market/risk/risk.py` — rolling annualized volatility (log returns, sqrt(252)), rolling beta, trailing max drawdown, liquidity, gap risk, debt-risk buckets
- Added `src/quant/factors/scoring.py` — §12 baseline weights, percentile-rank factor scores, renormalized overall score, stock ranking
- Fixed lint/type issues: trailing newlines, `zip(strict=True)`, long-line split, `universe_values: dict[str, list[float]]` typo
- Added `tests/unit/test_quant_factors.py` + `test_quant_scoring.py` (18 tests)
- Verified: ruff clean, mypy clean (5 source files), **140 total tests pass**
- Updated tasks.md (T007 complete, T008 next), current-state.md (Quant 90%), decisions.md

## 2026-09-14 — T006 Quant Engine: technical indicators (Phase 2)

- Added `src/market/technical/indicators.py` — pure-Python deterministic implementations:
  - `sma(close, period)` — Simple Moving Average
  - `ema(close, period)` — Exponential Moving Average (SMA-seeded, standard multiplier)
  - `rsi(close, period=14)` — Relative Strength Index (Wilder's smoothing)
  - `macd(close, fast=12, slow=26, signal=9)` — MACD line, signal, histogram
  - `bollinger_bands(close, period=20, num_std=2)` — upper, middle (SMA), lower
  - `atr(high, low, close, period=14)` — Average True Range (Wilder's smoothing)
  - `obv(close, volume)` — On-Balance Volume
  - `volume_sma(volume, period=20)` — Volume SMA
  - `relative_strength(close, benchmark_close)` — ratio vs benchmark
- Added `tests/unit/test_technical_indicators.py` (40 tests) — expected-value tests for each indicator
- Added `[tool.mypy.overrides]` for `tests.*` (relaxed strictness on test files)
- **Verified:** `ruff check` clean · `mypy` clean · `pytest` → **122 passed**

## 2026-09-13 — T002 data-source design + credentials plan (STEP 4)

- Added `docs/DATA_SOURCES.md`: per-domain provider selection (market, fundamental,
  valuation, macro, corporate events, news) with primary + fallback chains,
  valuation-as-computed decision, credentials plan, and a `TO VERIFY` list for T004.
- Added `configs/sources.yaml` — machine-readable provider registry (id, roles, auth,
  credential_env *names*, enabled/priority, per-domain selection + fallback chains).
- Extended `.env.example` with provider selectors (default `ssix_finipro`/`cafef`) and
  credential var **names** only (`FINIPRO_ACCESS_TOKEN`, `VIETSTOCK_API_KEY`,
  `TRADINGECONOMICS_API_KEY`) — no secrets committed.
- Added `tests/unit/test_sources_registry.py` (7 tests) validating registry structure,
  selection/fallback consistency, and the no-secrets policy.
- Updated `configs/README.md`, `helper/resources.md`, `README.md`, `project-context.md`.
- **Verification honesty:** network egress unavailable ⇒ provider endpoints/schemas
  could not be confirmed and are flagged `TO VERIFY` in T004 (KIS-006). PyYAML was
  installed into the local venv only, to actually execute (not skip) the registry tests;
  `pyproject.toml` untouched — adding it as a dev dependency needs approval.

## 2026-09-13 — STEP 2 DATABASE DESIGN implemented (T003)

- Added SQLAlchemy models (`src/common/models/`) covering every table in `docs/DATABASE_SCHEMA.md` — 38 tables, shared `Base` + naming convention + `Timestamp`/`Audit` mixins.
- Added initial Alembic migration `database/migrations/versions/0001_initial_schema.py` (creates all tables from model metadata + converts 12 time-series tables into TimescaleDB hypertables per §17).
- Wired `Base.metadata` into `database/migrations/env.py` (`target_metadata`).
- Added idempotent seeds (`database/seeds/`): exchanges (HOSE/HNX/UPCOM), 10 sectors + 15 industries, 30-row VN30 universe; wired into `database/seeds/run_all.py`.
- Added unit tests `tests/unit/test_models.py` (metadata contract, migration hypertable contract, seed data integrity); updated `test_smoke.py` seed test to be DB-free.
- **Decisions:** `predictions` kept as a regular table (Timescale unique-index rule vs `prediction_evaluations` FK); `signals` PK composite `(id, trade_date)`; VN30 seeded as baseline.
- **Verified:** `alembic upgrade head` → `downgrade base` → `upgrade head` all succeed on the running Docker TimescaleDB (38 tables, 12 hypertables); seeds insert correctly and are idempotent; `ruff` clean; `pytest` 11 passed; `mypy` clean on `src/common/models` + `database/seeds`.

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