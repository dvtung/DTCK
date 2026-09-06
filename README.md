# DTCK — AI Investment Research & Decision Intelligence Platform

> **AI does not replace investment judgment. AI increases the speed, consistency, depth and traceability of investment research.**

An AI-powered research & decision-support platform for the **Vietnam stock market** (HOSE / HNX / UPCOM), starting with the VN30 universe.

**⚠️ Not an auto-trading system.** The platform produces *evidence-backed research, scores, and risk assessment* — a human always makes the investment decision (spec §4.6).

---

## Pipeline

```text
DATA → QUANT → BACKTEST → ML → RAG → AI AGENT → EVIDENCE → RISK CONTROL → HUMAN
```

Principles (spec §4): **Data First** · **Deterministic Calculation First** (LLM never computes RSI/P/E/ROE/…) · **LLM Is a Reasoning Layer** · **Evidence-Based Reasoning**. Strategies must be **backtested before deployment**.

---

## Repository layout (spec §35)

```text
apps/          api (FastAPI) · dashboard (Streamlit) · worker (schedulers/ingest)
src/           data · market · quant · ml · rag · agents · evidence · portfolio · backtesting · common
database/      alembic migrations + seeds
tests/         unit · integration · data_quality · agent · e2e
docs/          architecture & specifications (see below)
memory-bank/   cross-session project memory (§37)
helper/        operational guides (deployment, resources)
notebooks/     research
configs/       configuration
scripts/       ops scripts
offline_package/  offline wheels for air-gapped installs
docker/        Dockerfiles + compose
```

## Documentation

| Doc | Content |
|---|---|
| `docs/SYSTEM_SPECIFICATION.md` | **The spec** (v1.0, 58 sections) — read this first |
| `docs/AI_INVESTMENT_CONCEPT.md` | Earlier concept draft (Vietnamese) |
| `docs/ARCHITECTURE.md` | Logical architecture, components, phases, MVP gates |
| `docs/DATABASE_SCHEMA.md` | Full PostgreSQL/TimescaleDB schema |
| `docs/DATA_ARCHITECTURE.md` | Data domains, ingestion, quality framework |
| `docs/QUANT_ENGINE.md` | Deterministic factor & scoring engine |
| `docs/BACKTESTING.md` | Backtest pipeline, bias prevention, metrics |
| `docs/ML_ARCHITECTURE.md` | XGBoost/LightGBM pipeline, registry, calibration |
| `docs/RAG_ARCHITECTURE.md` | Qdrant ingestion + hybrid retrieval + evidence |
| `docs/AGENT_ARCHITECTURE.md` | LangGraph agents, tools, structured output |
| `docs/API_SPECIFICATION.md` | REST API groups `/api/v1/*` |
| `docs/DEPLOYMENT.md` | Setup & deployment |
| `docs/SECURITY.md` | Secrets, auth, audit, RBAC |
| `memory-bank/` | Project memory (§37): context, state, decisions, issues, tasks, changelog |

## Quick start (MVP)

```bash
cp .env.example .env        # fill real values
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api python -m database.seeds.run_all
```

- API docs → http://localhost:8000/docs
- Dashboard → http://localhost:8501

See `docs/DEPLOYMENT.md` and `helper/deployment.md` for details.

## Development roadmap (spec §57)

**Spec (100%) → Database design → Repo structure → Data sources → Data ingestion → Quant Engine → Backtest → RAG → AI Agent → ML → Portfolio → Production**

> **Không chuyển sang Agent trước khi Data + Quant + Backtest đạt baseline có thể kiểm chứng.** (No agent work before a verifiable Data+Quant+Backtest baseline.)

## Status

```text
Specification: ████████████████████ 100%
Architecture:  ████████████████████ 100%   (docs drafted)
Database:      ████████████████████ 100%   (schema docs drafted; migrations pending)
Data/Analysis: ░░░░░░░░░░░░░░░░░░░░   0%   ← next
```

See `memory-bank/current-state.md` and `memory-bank/tasks.md`.