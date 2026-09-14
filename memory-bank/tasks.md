# Memory Bank — Tasks

**Last updated:** 2026-09-13

Legend: `[ ]` To Do · `[~]` In Progress · `[x]` Completed · `[!]` Blocked

---

## Current

- [x] **T001 — Phase 0 scaffold + docs** — repo structure, docs set, memory bank, pyproject/compose/env/README. *(2026-09-06)*
- [x] **T003 — Alembic migrations (STEP 2 DATABASE DESIGN) + seeds** — `src/common/models/` (38 tables), migration `0001_initial_schema.py` (+ TimescaleDB hypertables), idempotent seeds (exchanges/sectors/industries/VN30). Verified up→down→up + seeds against running TimescaleDB. *(2026-09-13)*
- [x] **T002 — Data-source design + credentials plan (STEP 4)** — `docs/DATA_SOURCES.md` (provider selection per domain, fallback chains, credentials plan) + `configs/sources.yaml` (machine-readable registry) + `.env.example` provider vars + `tests/unit/test_sources_registry.py`. Provider endpoints marked `TO VERIFY` for T004 (no network egress to confirm). *(2026-09-13)*
- [x] **T004 — Data collectors → validators → normalizers → pipeline (Phase 1)** — `src/data/` package (collectors, validators, normalizers, pipelines, providers, fixture, quality, records). FixtureProvider for offline deterministic testing. Worker CLI wired. `tests/unit/test_pipeline.py` (38 tests). Verified: ruff clean, mypy clean, 82 total tests pass. *(2026-09-14)*
- [x] **T005 — Data quality framework (scoring + gates, §39)** — `src/data/quality.py` (6-dimension scoring: completeness/validity/consistency/uniqueness/freshness/accuracy, weighted mean with renormalization, threshold gate). `tests/unit/test_quality.py` (26 tests). Verified: ruff clean, mypy clean, 82 total tests pass. *(2026-09-14)*

## Backlog (ordered per spec §57)

- [x] **T006 — Quant Engine: technical indicators (+ expected-value unit tests)** — `src/market/technical/indicators.py` (SMA, EMA, RSI, MACD, Bollinger Bands, ATR, OBV, volume SMA, relative strength). Pure-Python deterministic implementations. `tests/unit/test_technical_indicators.py` (40 tests). Verified: ruff clean, mypy clean, 122 total tests pass. *(2026-09-14)*

## Backlog (ordered per spec §57)

- [x] **T007 — Quant Engine: fundamental factors, valuation, momentum, risk + factor scores** — `src/market/fundamental/factors.py` (growth/profitability/leverage/cashflow/quality), `src/market/valuation/valuation.py` (P-E/P-B/EV/PEG/yield + percentile ranks), `src/market/momentum/momentum.py` (n-day returns/volume expansion/relative momentum), `src/market/risk/risk.py` (volatility/beta/drawdown/liquidity/gap/debt-risk), `src/quant/factors/scoring.py` (§12 baseline weights + percentile-rank aggregation + ranking). Pure-Python deterministic. `tests/unit/test_quant_factors.py` + `test_quant_scoring.py` (18 tests). Verified: ruff clean, mypy clean, 140 total tests pass. *(2026-09-14)*
- [ ] T008 — Scoring engine (baseline weights, §12) + ranking + explainability payloads — **next**
- [ ] T009 — Backtesting engine (walk-forward, costs, bias controls) + metrics
- [ ] T010 — FastAPI `apps/api` exposing `/api/v1/*` per docs/API_SPECIFICATION.md (MVP-1 read paths)
- [ ] T011 — Streamlit dashboard (market overview, screener, ranking, stock detail)
- [ ] T012 — News ingestion + RAG (Qdrant) + evidence engine (Phase 4 → MVP-2)
- [ ] T013 — LangGraph agents + orchestrator + audit (Phase 5)
- [ ] T014 — ML feature dataset + XGBoost/LightGBM + calibration + registry (Phase 6)
- [ ] T015 — Production: auth, monitoring, alerts, CI/CD, hardening (Phase 7)

---

## Blocked until Data+Quant+Backtest baseline (spec §57)

> "Không chuyển sang Agent trước khi Data + Quant + Backtest đạt baseline có thể kiểm chứng."

- [ ] T013 — Agents (blocked)
- [ ] T014 — ML prediction (blocked)