# Memory Bank — Changelog

**Last updated:** 2026-09-14

## 2026-09-14 — Standing rule: htmldocs updated with every source change

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