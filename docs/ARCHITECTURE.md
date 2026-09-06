# ARCHITECTURE

## AI Investment Research & Decision Intelligence Platform

**Version:** 1.0
**Status:** Baseline — derived from SYSTEM_SPECIFICATION.md v1.0 (§7)

---

# 1. System Philosophy

```text
                  ┌──────────────┐
                  │    DATA      │
                  └──────┬───────┘
                         ↓
                  ┌──────────────┐
                  │    QUANT     │
                  └──────┬───────┘
                         ↓
                  ┌──────────────┐
                  │   BACKTEST   │
                  └──────┬───────┘
                         ↓
                  ┌──────────────┐
                  │     ML       │
                  └──────┬───────┘
                         ↓
                  ┌──────────────┐
                  │     RAG      │
                  └──────┬───────┘
                         ↓
                  ┌──────────────┐
                  │  AI AGENT    │
                  └──────┬───────┘
                         ↓
                  ┌──────────────┐
                  │   EVIDENCE   │
                  └──────┬───────┘
                         ↓
                  ┌──────────────┐
                  │ RISK CONTROL │
                  └──────┬───────┘
                         ↓
                  ┌──────────────┐
                  │    HUMAN     │
                  └──────────────┘
```

Core principle (spec §56):

> **AI does not replace investment judgment. AI increases the speed, consistency, depth and traceability of investment research.**

Four binding design principles (§4):

1. **Data First** — bad data → bad features → bad model → bad agent. Data quality gates usage.
2. **Deterministic Calculation First** — every financial/quant computation (RSI, P/E, ROE, …) runs in a software engine, never in an LLM.
3. **LLM Is a Reasoning Layer** — the LLM plans, selects tools, synthesizes, interprets; it is **not** a source of truth and may never fabricate financial figures.
4. **Evidence-Based Reasoning** — every claim → evidence → source → timestamp → data version (§19).

Plus: Backtest Before Deployment (§4.5), Human-in-the-loop (§4.6), Full Auditability (§4.7).
# 2. Logical Architecture (§7.1)

```text
┌───────────────────────────────────────────────┐
│                 DATA SOURCES                 │
│                                               │
│ Market │ Financial │ News │ Macro │ Events   │
└───────────────────────┬───────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│              DATA INGESTION                   │
│                                               │
│ API / ETL / Collector / Scheduler             │
└───────────────────────┬───────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│                DATA PLATFORM                  │
│                                               │
│ Raw │ Clean │ Curated │ Feature │ Documents   │
└──────────────┬───────────────────────┬────────┘
               │                       │
               ▼                       ▼
       ┌───────────────┐       ┌──────────────┐
       │ QUANT ENGINE  │       │ RAG ENGINE   │
       └───────┬───────┘       └──────┬───────┘
               │                       │
               ▼                       ▼
       ┌───────────────┐       ┌──────────────┐
       │ ML ENGINE     │       │ EVIDENCE     │
       │               │       │ ENGINE       │
       └───────┬───────┘       └──────┬───────┘
               │                       │
               └───────────┬───────────┘
                           ▼
                 ┌───────────────────┐
                 │ INVESTMENT ENGINE │
                 └─────────┬─────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │   AI AGENT LAYER  │
                 │                   │
                 │ Research Agent    │
                 │ Analysis Agent    │
                 │ Monitoring Agent  │
                 │ Portfolio Agent   │
                 └─────────┬─────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │ LLM ORCHESTRATOR  │
                 └─────────┬─────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │ RISK / GUARDRAIL  │
                 └─────────┬─────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │ HUMAN / DASHBOARD │
                 └───────────────────┘
```
---

# 3. Major Components (§8)

## 3.1. Data Ingestion Layer

- Collectors (per source), schedulers, validators, normalizers.
- Pipeline: `Source → Collector → Validator → Normalizer → PostgreSQL`.
- Runs inside **worker** process (APScheduler / cron); supports retry + error handling.
- Future: Kafka streaming, Airflow/Dagster orchestration (ADR-004 defers these).

## 3.2. Data Platform

- **PostgreSQL + TimescaleDB** — primary structured store (ADR-003). Hypertables for all time-series (see DATABASE_SCHEMA.md §17).
- **Qdrant** — vector store for news/reports/disclosures (ADR-002).
- Future: S3-compatible object storage for raw documents & backtest artifacts (§9.3).

## 3.3. Quant Engine

- Pure-Python deterministic calculation of technical, fundamental, valuation, momentum, risk factors.
- No LLM calls. Fully unit-tested against expected values (§38).
- Outputs factor scores (0-100) and the multi-factor **overall score** (baseline weights §12: Fundamental 30% / Technical 20% / Momentum 15% / Valuation 15% / Quality 10% / Risk 10%).
- See `docs/QUANT_ENGINE.md`.

## 3.4. ML Engine

- XGBoost / LightGBM / scikit-learn.
- Targets: `P(return>0)`, `P(return>5%)`, `P(return>10%)`, expected return, volatility.
- Registry-backed governance (§40): model version, feature version, data version, metrics, status.
- See `docs/ML_ARCHITECTURE.md`.

## 3.5. Backtesting Engine

- First-class component (ADR-007). Walk-forward, rolling, transaction cost, slippage, corporate actions.
- Prevents look-ahead / survivorship bias & data leakage (§17).
- See `docs/BACKTESTING.md`.

## 3.6. RAG Engine

- Document ingestion → embedding → Qdrant → hybrid retrieval (vector + keyword) → recency weight → source reliability → reranking → evidence set (§18.2).
- See `docs/RAG_ARCHITECTURE.md`.

## 3.7. Evidence Engine

- Every claim carries `source, source_type, published_at, data_timestamp, evidence_text, confidence` (§19).
- Linked to analyses, predictions, agent runs, reports.

## 3.8. AI Agent Layer

- Research / Analysis / Monitoring / Portfolio agents + Orchestrator (§20, §21).
- LangGraph-based; structured outputs (§23).
- See `docs/AGENT_ARCHITECTURE.md`.

## 3.9. Risk / Guardrail Layer (§42)

- Detects: low data quality, model drift, extreme volatility, low liquidity, conflicting signals, insufficient evidence, stale data, unexpected model output.
- Escalation: `Normal → Warning → Reduced Confidence` or `Critical Risk → Block Recommendation`.
---

# 4. Tool Architecture (§22)

LLM never touches the database directly. It goes through an application service layer:

```text
LLM
 ↓
Tool Call
 ↓
Application Service
 ↓
Database / Quant Engine / RAG
 ↓
Structured Result
 ↓
LLM
```

Tool catalog (MVP): `get_stock_price`, `get_technical`, `get_fundamentals`, `get_valuation`, `get_peer_analysis`, `get_market_regime`, `get_news`, `get_corporate_events`, `get_prediction`, `get_risk`.

---

# 5. Runtime Topology

## MVP (Docker Compose) — §33

```text
┌──────────────────────────┐
│ FastAPI                  │
├──────────────────────────┤
│ Worker (scheduler/ingest)│
├──────────────────────────┤
│ PostgreSQL (TimescaleDB) │
├──────────────────────────┤
│ Qdrant                   │
├──────────────────────────┤
│ Streamlit (dashboard)    │
└──────────────────────────┘
```

## Production (future)

```text
Load Balancer → FastAPI → Task Queue → Workers → PostgreSQL/TimescaleDB → Qdrant → Object Storage
```

---

# 6. Repository Layout (§35)

```text
apps/       api (FastAPI), dashboard (Streamlit), worker (schedulers/ingest)
src/        data, market (technical/fundamental/valuation/momentum/risk), quant,
            ml, rag, agents, evidence, portfolio, backtesting, common
database/   alembic migrations + seeds
tests/      unit, integration, data_quality, agent, e2e
notebooks/  research & experiments
configs/    environment/config files
scripts/    ops scripts
docs/       architecture documentation
memory-bank/ cross-session project memory
offline_package/ pre-downloaded offline wheels (air-gapped installs)
docker/     Dockerfiles + compose
```

---

# 7. API Surface (§28)

```text
/api/v1/market
/api/v1/stocks
/api/v1/fundamentals
/api/v1/technical
/api/v1/valuation
/api/v1/news
/api/v1/analysis
/api/v1/predictions
/api/v1/portfolio
/api/v1/backtests
/api/v1/agents
```

See `docs/API_SPECIFICATION.md`.

---

# 8. Development Phases & MVP Gates (§48–§52)

| Phase | Deliverables | MVP |
|---|---|---|
| 0 — Specification | SYSTEM_SPECIFICATION, ARCHITECTURE, DATABASE_SCHEMA | — |
| 1 — Data Foundation | PostgreSQL, market/historical data, validation, pipeline | MVP-1 partial |
| 2 — Quant Engine | technical/fundamental/valuation/risk/factor/scoring engines | MVP-1 |
| 3 — Backtesting | walk-forward, transaction cost, performance reports | MVP-1 |
| 4 — RAG | ingestion, embedding, Qdrant, hybrid retrieval, reranking | MVP-2 |
| 5 — AI Agent | 4 agents + orchestrator | MVP-2 |
| 6 — ML | feature dataset, XGBoost/LightGBM, calibration, registry | MVP-3 |
| 7 — Production | FastAPI, dashboard, auth, monitoring, alert, audit, Docker, CI/CD | Production |

**MVP-1 does NOT require an LLM Agent.** The spec (§49) is explicit: data → quant → score → ranking → backtest → dashboard.

---

# 9. Cross-Cutting Concerns

- **Observability (§46):** CPU/memory/disk/DB/API latency/worker status/LLM latency & cost/agent failures/pipeline failures/model performance/data freshness.
- **Cost Control (§47):** LLM never used for deterministic tasks; minimize LLM calls, maximize information value.
- **Security (§32):** API auth, secret management, RBAC, audit logging; no API keys/passwords/secrets in source, git, or Docker images. See `docs/SECURITY.md`.
- **Model & Agent Governance (§40–§41):** registries, statuses, explicit forbidden actions for agents.