# Memory Bank — Active Task

## Workstreams W1, W1b, W2: DB Read Path, Quant Factor Scoring, CaféF RSS Ingestion (2026-09-25)

**State:** COMPLETED
**Goal:** Connect FastAPI read path to TimescaleDB (W1), implement daily quant factor scoring job (W1b), and wire live news ingestion from CaféF RSS without external credentials (W2).

### Deliverables & Verification:
- [x] **W1 (DB Read Path)**:
  - Created `apps/api/services/market_source.py` protocol + `DbMarketService` in `apps/api/services/db_market.py`.
  - Added `ranking_payload.py` to decouple ranking schema conversions from the in-memory vs DB source.
  - Configured `MARKET_DATA_SOURCE=memory|db|auto` in `apps/api/dependencies.py` and `apps/api/config.py`.
  - Updated routers (`fundamentals`, `valuation`, `technical`, `news`) to consume `MarketSource`.
  - Unit tests: `tests/unit/test_market_data_source.py`.
  - Integration tests: `tests/integration/test_db_market.py` against live PostgreSQL/TimescaleDB.
- [x] **W1b (Scoring Job)**:
  - Created `src/quant/scoring/job.py` calculating raw price-derived factors (RSI-14, 63-day momentum, negated 20-day volatility) and upserting into `factor_scores` with honest `NULL` values for unavailable dimensions.
  - Added `compute-scores` command to `apps/worker/cli.py`.
  - Unit tests: `tests/unit/test_scoring_job.py`.
  - Integration tests: `tests/integration/test_scoring_job.py`.
- [x] **W2 (CaféF RSS Provider & News Linking)**:
  - Captured live XML fixture (`tests/fixtures/cafef_rss_sample.xml`).
  - Implemented stdlib RSS/Atom parser and `RssNewsProvider` in `src/data/providers/rss.py`.
  - Registered `cafef` provider in `configs/sources.yaml` (`VERIFIED_2026-09-25`) and `src/data/providers/registry.py`.
  - Supported multi-symbol ticker extraction and symbol filtering in `src/rag/ingestion/chunking.py` and `src/rag/retrieval/store.py`.
  - Wired ticker matching into worker news ingestion (`apps/worker/cli.py`).
  - Unit tests: `tests/unit/test_rss_provider.py` (MockTransport + XML fixture parsing + date handling).
  - Live verification: ingested 50 real articles from CaféF; confirmed stored in `news` and linked in `news_symbols`; validated `/api/v1/news`, `/api/v1/rag/search`, and `/api/v1/evidence`.
- [x] **Quality Gate**:
  - `ruff check .` -> All checks passed!
  - `mypy` -> Success: no issues found in 125 source files.
  - `pytest` -> 399 passed, 2 skipped in ~3.0s.


**State:** COMPLETED
**Goal:** API starts with reproducible ML dependencies in Docker; preserve public ML imports.
**Scope:** API/worker Dockerfiles, lazy ML package exports, regression tests and deployment docs.
**Constraints:** Preserve existing Compose edits and database volumes; use existing `[ml]` extra.

- [x] Build API/worker images: `BUILD_EXIT_CODE=0`.
- [x] Recreate only API/worker with `docker compose up -d --no-deps api worker`.
- [x] API imports sklearn 1.9.1, xgboost 2.1.4, lightgbm 4.7.0; worker imports ModelTrainer.
- [x] Container `/healthz` and `/api/v1/predictions/VNM` return HTTP 200.
- [x] Lint, types and unit regression tests (including blocked optional ML imports).
  - `ruff check .` clean · `mypy src apps` clean (119 files) · `pytest tests/unit` **343 passed, 1 skipped**
    (run with `LLM_PROVIDER=mock`; local `.env` sets `ollama`, which the smoke-test allowlist rejects)
  - In-container: `import sklearn` → 1.9.1; blocked-import smoke proves `apps.api.main`
    imports without sklearn and `src.ml.training` stays lazy.

## Previous task


**ID:** `T014 — ML prediction: feature dataset + training + calibration + registry + predictions API (Phase 6)`
**State:** COMPLETED (2026-09-16)

**Goal:** Classically-trained prediction per spec §14/§15/§26/§40 + `docs/ML_ARCHITECTURE.md`: as-of feature dataset (no leakage), XGBoost training with temporal splits, Platt-style calibration, versioned model registry with status lifecycle, `/api/v1/predictions` endpoints, worker `train-model` CLI.

**Scope:** `src/ml/` (feature_dataset, training, model_registry, predictor, schemas), `apps/api/routers/predictions.py`, `apps/worker/cli.py` (train-model), `tests/unit/test_ml_*.py`, `test_t014_t015.py`.

**Constraints:** Deterministic offline-first; sklearn 1.8+ compatible (no `CalibratedClassifierCV cv="prefit"`); no target leakage in features.

**Key fixes during implementation:**
- **Target leakage removed:** `horizon_return_*` forward-return columns were in the feature matrix (`horizon_return_5d` == target exactly); deleted from features, kept only in targets. Regression tests prove features are invariant to future price shocks.
- **Duplicate-date split bug:** temporal split used row counts; a date could land in two partitions. Now splits on unique trade dates; guards reject single-class partitions, misaligned frames, and non-0/1 labels.
- **`hash()` symbol feature** was process-randomized (PYTHONHASHSEED) → replaced with `zlib.crc32`.
- **KI-012 (new):** the synthetic market fixture is monotonically rising → 100% positive 5-day labels; a real classifier cannot be fit. `train()`/`train-model` fail loudly instead of emitting a fake model; predictor serves a deterministic fallback stub. Real training is blocked on DB wiring (KI-006/007/008).

**Acceptance:**
- [x] `ruff check .` clean
- [x] `mypy` clean — "Success: no issues found in 119 source files"
- [x] `pytest -q` — **325 passed** (+12 ML/API tests; leakage + training contract)
- [x] `docs/htmldocs/status.html` updated (ML 80%, KI-012, roadmap → T015)
- [x] memory-bank updated (active-task/current-state/changelog/tasks)
