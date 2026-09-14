# Memory Bank — Current State

**Last updated:** 2026-09-06

---

## 1. Status per spec §58

```text
Specification:  ████████████████████ 100%   (docs/SYSTEM_SPECIFICATION.md, v1.0)
Architecture:   ████████████████████ 100%   (docs/ARCHITECTURE.md drafted)
Database:       ████████████████████ 100%   (schema + Alembic migration 0001 + seeds DONE)
Data Pipeline:  ████████████████████ 100%   (T004+T005: collectors/validators/normalizers/pipeline + quality framework DONE)
Quant Engine:   ██████████████████░░   90%   (T006 indicators + T007 factors/valuation/momentum/risk/scoring DONE; T008 payloads pending)
Backtesting:    ░░░░░░░░░░░░░░░░░░░░   0%
RAG:            ░░░░░░░░░░░░░░░░░░░░   0%
AI Agent:       ░░░░░░░░░░░░░░░░░░░░   0%
ML:             ░░░░░░░░░░░░░░░░░░░░   0%
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
- Tests: 140 total pass (82 pipeline/quality + 40 technical + 18 T007 factors/scoring); ruff + mypy clean.
- **Fundamental factors** (`src/market/fundamental/factors.py`) — revenue/EPS growth, ROE, ROA, margins, D/E, interest coverage, FCF, FCF margin, earnings quality. All return `None` on zero denominators.
- **Valuation** (`src/market/valuation/valuation.py`) — P/E, forward P/E, P/B, EV/EBITDA, EV/Sales, dividend yield, PEG, enterprise value + percentile ranks (industry/historical).
- **Momentum** (`src/market/momentum/momentum.py`) — n-day returns, multi-period, volume expansion, relative momentum vs benchmark.
- **Risk** (`src/market/risk/risk.py`) — rolling annualized volatility (log returns), beta, trailing max drawdown, liquidity, gap risk, debt-risk buckets.
- **Factor scoring** (`src/quant/factors/scoring.py`) — §12 baseline weights (fund 0.30/tech 0.20/mom 0.15/val 0.15/qual 0.10/risk 0.10), percentile-rank aggregation, renormalized overall score, stock ranking.
- **Technical indicators** (`src/market/technical/indicators.py`) — SMA, EMA, RSI (Wilder's smoothing), MACD (12/26/9), Bollinger Bands (20, 2σ), ATR (14), OBV, volume SMA, relative strength vs benchmark. Pure-Python, deterministic, tested against hand-computed expected values (40 tests).
- Git repo on branch `feat/data-source-design`.

---

## 3. Active Task

**ID:** `T007 — Quant Engine: fundamental/valuation/momentum/risk + scoring`
**State:** COMPLETED (2026-09-14)

**Prior tasks:** `T001 — Phase 0 scaffold` (2026-09-06) · `T003 — migrations+seeds` (2026-09-13) · `T002 — data-source design` (2026-09-13) · `T004+T005 — pipeline+quality` (2026-09-14) · `T006 — technical indicators` (2026-09-14)

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
6. QUANT ENGINE           → T006 DONE (technical indicators, 2026-09-14) · T007 next (fundamental/valuation/momentum/risk)
6. BACKTEST ENGINE
7. RAG
8. AI AGENT               ← NOT before Data+Quant+Backtest baseline (§57)
9. ML PREDICTION
10. PORTFOLIO INTELLIGENCE
11. PRODUCTION
```