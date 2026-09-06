# Memory Bank — Tasks

**Last updated:** 2026-09-06

Legend: `[ ]` To Do · `[~]` In Progress · `[x]` Completed · `[!]` Blocked

---

## Current

- [x] **T001 — Phase 0 scaffold + docs** — repo structure, docs set, memory bank, pyproject/compose/env/README. *(2026-09-06)*

## Backlog (ordered per spec §57)

- [ ] T002 — Data-source design (Vietnam market/financial/news providers) + credentials plan [depends: T001]
- [ ] T003 — Alembic migrations implementing `docs/DATABASE_SCHEMA.md` + seeds (exchanges, sectors, VN30)
- [ ] T004 — Data collectors → validators → normalizers → pipeline (Phase 1)
- [ ] T005 — Data quality framework (scoring + gates, §39)
- [ ] T006 — Quant Engine: technical indicators (+ expected-value unit tests)
- [ ] T007 — Quant Engine: fundamental factors, valuation, momentum, risk + factor scores
- [ ] T008 — Scoring engine (baseline weights, §12) + ranking + explainability payloads
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