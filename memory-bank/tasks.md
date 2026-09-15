# Memory Bank — Tasks

**Last updated:** 2026-09-15

Legend: `[ ]` To Do · `[~]` In Progress · `[x]` Completed · `[!]` Blocked

> **Standing rule (all tasks):** every task that changes source code, schema,
> configs, or behavior MUST also update `docs/htmldocs/` (Vietnamese) in the
> same task — status page, module reference, and any other affected page —
> and re-validate the HTML before marking the task complete.

---

## Current

- [x] **T001 — Phase 0 scaffold + docs** — repo structure, docs set, memory bank, pyproject/compose/env/README. *(2026-09-06)*
- [x] **T003 — Alembic migrations (STEP 2 DATABASE DESIGN) + seeds** — `src/common/models/` (38 tables), migration `0001_initial_schema.py` (+ TimescaleDB hypertables), idempotent seeds (exchanges/sectors/industries/VN30). Verified up→down→up + seeds against running TimescaleDB. *(2026-09-13)*
- [x] **T002 — Data-source design + credentials plan (STEP 4)** — `docs/DATA_SOURCES.md` (provider selection per domain, fallback chains, credentials plan) + `configs/sources.yaml` (machine-readable registry) + `.env.example` provider vars + `tests/unit/test_sources_registry.py`. Provider endpoints marked `TO VERIFY` for T004 (no network egress to confirm). *(2026-09-13)*
- [x] **T004 — Data collectors → validators → normalizers → pipeline (Phase 1)** — `src/data/` package (collectors, validators, normalizers, pipelines, providers, fixture, quality, records). FixtureProvider for offline deterministic testing. Worker CLI wired. `tests/unit/test_pipeline.py` (38 tests). Verified: ruff clean, mypy clean, 82 total tests pass. *(2026-09-14)*
- [x] **T005 — Data quality framework (scoring + gates, §39)** — `src/data/quality.py` (6-dimension scoring: completeness/validity/consistency/uniqueness/freshness/accuracy, weighted mean with renormalization, threshold gate). `tests/unit/test_quality.py` (26 tests). Verified: ruff clean, mypy clean, 82 total tests pass. *(2026-09-14)*

## Backlog (ordered per spec §57)


- [x] **T006 — Quant Engine: technical indicators (+ expected-value unit tests)** — `src/market/technical/indicators.py` (SMA, EMA, RSI, MACD, Bollinger Bands, ATR, OBV, volume SMA, relative strength). Pure-Python deterministic implementations. `tests/unit/test_technical_indicators.py` (40 tests). Verified: ruff clean, mypy clean, 122 total tests pass. *(2026-09-14)*
- [x] **T007 — Quant Engine: fundamental factors, valuation, momentum, risk + factor scores** — `src/market/fundamental/factors.py` (growth/profitability/leverage/cashflow/quality), `src/market/valuation/valuation.py` (P-E/P-B/EV/PEG/yield + percentile ranks), `src/market/momentum/momentum.py` (n-day returns/volume expansion/relative momentum), `src/market/risk/risk.py` (volatility/beta/drawdown/liquidity/gap/debt-risk), `src/quant/factors/scoring.py` (§12 baseline weights + percentile-rank aggregation + ranking). Pure-Python deterministic. `tests/unit/test_quant_factors.py` + `test_quant_scoring.py` (18 tests). Verified: ruff clean, mypy clean, 140 total tests pass. *(2026-09-14)*
- [x] **D1 — Static HTML docs site** — `docs/htmldocs/` (index/structure/status/modules/database/pipeline + style.css). Project intro, repo layout, dev status per spec §58, full module reference with signatures + usage examples. All pages HTML-validated, nav links verified. *(2026-09-14)*
- [x] **T008 — Scoring engine (baseline weights §12) + ranking + explainability payloads** — `src/quant/scoring/engine.py` (`FactorContribution`, `ScoreDecomposition`, `StockRanking`, `decompose_score`, `score_universe`, `build_signal_label`, `build_confidence`). Per-factor contributions with renormalized weights, ranked universe, POSITIVE/NEUTRAL/NEGATIVE labels + confidence. `tests/unit/test_scoring_engine.py` (11 tests). *(2026-09-15)*
- [x] **T009 — Backtesting engine (walk-forward, costs, bias controls) + metrics** — `src/backtesting/` — `models.py` (PriceBar/BacktestData/ExecutionCosts/Trade/EquityPoint/BacktestConfig/BacktestResult), `metrics.py` (11 chỉ số: total return, CAGR, annualized volatility, Sharpe, Sortino, max drawdown, Calmar, win rate, profit factor, turnover, transaction-cost total + aggregate `compute_metrics`), `engine.py` (`run_backtest`/`select_window`/rebalance/close-leg), `walkforward.py` (`walk_forward_windows`/`rolling_windows`). `tests/unit/test_backtesting.py` (10 tests). *(2026-09-15)*
- [x] **T010 — FastAPI `apps/api` exposing `/api/v1/*`** — `main.py` (health/readyz) + 7 routers (`market`, `stocks`, `fundamentals`, `technical`, `valuation`, `news`, `backtests`) = 23 paths / 24 operations per `docs/API_SPECIFICATION.md`; `schemas.py` (21 Pydantic models incl. generic `Page[T]`), `dependencies.py` (`MarketDep`), `services/market_data.py` (deterministic in-memory service — KI-008), `routers/common.py` (pagination + `not_found` envelope). `tests/unit/test_api.py` (14 tests). *(2026-09-15)*

- [x] **T011 — Streamlit dashboard (T011)** — `apps/dashboard/` — `client.py` (HTTP-first `MarketClient` + in-process `MarketService` fallback), `components.py` (framework-agnostic formatting/transforms), `app.py` (6 pages: overview/screener/rankings/detail/backtests/health via Streamlit + plotly). `tests/unit/test_dashboard.py` (34 tests). Verified: ruff clean, mypy clean, 209 total tests pass. *(2026-09-15)*

- [x] **T012 — News ingestion + RAG + evidence engine (Phase 4 → MVP-2)** — `src/rag/` (embedding `hash_embed.py` HashEmbedding, ingestion `chunking.py`, retrieval `store.py` MemoryVectorStore + optional QdrantAdapter + `retriever.py` hybrid, `reranking/reranker.py`, `service.py` RagService singleton), `src/evidence/engine.py` (Evidence + confidence_for + build_evidence §19), `apps/api/routers/rag.py` (3 endpoints: `/api/v1/rag/search`, `/api/v1/rag/status`, `/api/v1/evidence` — API total 26 paths / 27 ops), `apps/api/services/rag_service.py` (seeds from MarketService news on first use), `readyz` gains qdrant status. `tests/unit/test_rag_evidence.py` (20) + test_api.py (+3) = +23 tests. Verified: ruff clean, mypy clean (102 files), 232 total tests pass. *(2026-09-15)*
- [ ] T013 — LangGraph agents + orchestrator + audit (Phase 5)
- [ ] T014 — ML feature dataset + XGBoost/LightGBM + calibration + registry (Phase 6)
- [ ] T015 — Production: auth, monitoring, alerts, CI/CD, hardening (Phase 7)

---

## Blocked until Data+Quant+Backtest baseline (spec §57)

> "Không chuyển sang Agent trước khi Data + Quant + Backtest đạt baseline có thể kiểm chứng."

- [ ] T013 — Agents (blocked)
- [ ] T014 — ML prediction (blocked)