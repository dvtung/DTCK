# DEPLOYMENT

## AI Investment Research & Decision Intelligence Platform

**Version:** 1.0
**Status:** Baseline — MVP deployment via Docker Compose (§33)

---

# 1. Topology (MVP)

```text
┌──────────────────────────┐
│ FastAPI (apps/api)       │
├──────────────────────────┤
│ Worker (apps/worker)     │   schedulers + ingestion + quant daily jobs
├──────────────────────────┤
│ PostgreSQL + TimescaleDB │
├──────────────────────────┤
│ Qdrant                   │
├──────────────────────────┤
│ Streamlit (apps/dashboard)│
└──────────────────────────┘
```

All behind the Compose network; only necessary ports published to host.

---

# 2. Local Setup

```bash
# 1. Clone & enter project
cd ai-investment-platform

# 2. Environment
cp .env.example .env          # fill in real values (never commit .env)

# 3. Start infra + apps
docker compose up --build -d

# 4. Run migrations
docker compose exec api alembic upgrade head

# 5. Seed reference data
docker compose exec api python -m database.seeds.run_all

# 6. Check services
docker compose ps
```

Access:
- API: http://localhost:8000/docs
- API health: http://localhost:8000/healthz
- Dashboard: http://localhost:8501
- Qdrant dashboard: http://localhost:6333/dashboard

### Local development (no Docker)

For T010 read endpoints and T008/T009 engines, a full Docker stack is **not** required:

```bash
# activate the local venv (.venv)
source .venv/bin/activate

# API (in-memory deterministic service — KI-008, no DB needed)
uvicorn apps.api.main:app --reload       # http://localhost:8000/docs

# run all unit tests
pytest -q

# run just the API tests (uses TestClient, no server needed)
pytest tests/unit/test_api.py -q
```

---

# 3. Environment Variables

Core variables (full list in `.env.example`):

| Variable | Purpose |
|---|---|
| `POSTGRES_USER/DB/PASSWORD` | DB credentials |
| `DATABASE_URL` | SQLAlchemy connection string |
| `QDRANT_URL` | Qdrant gRPC/HTTP endpoint |
| `LLM_PROVIDER` / `LLM_API_KEY` / `LLM_MODEL` | provider abstraction (ADR-005) |
| `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` | embedding service |
| `REDIS_URL` (optional) | cache/queue (future) |
| `LOG_LEVEL` | logging verbosity |

Never commit real values; never bake into images.

---

# 4. Migrations

- Tool: **Alembic**; files in `database/migrations/`.
- TimescaleDB hypertables are created inside the same migration after `CREATE TABLE`.
- Never edit a merged migration; add a new one.
- Seeds in `database/seeds/` (exchanges, sectors, VN30 memberships, sample fixtures for tests).

---

# 5. Health Checks & Observability (§46)

| Service | Health probe |
|---|---|
| api | `GET /healthz` (DB + Qdrant connectivity) |
| worker | heartbeat table row / `GET /workers` status |
| db | `pg_isready` (compose healthcheck) |
| qdrant | `GET /readyz` |

Logs: structured JSON (api, worker, pipeline). Metrics tracked: CPU, memory, disk, DB, API latency, worker status, LLM latency/cost, agent failures, pipeline failures, model performance, data freshness.

---

# 6. Running Jobs

- Scheduler (APScheduler) runs inside worker: EOD market data, foreign flow, news, feature/scoring recompute, regime update.
- For offline experimentation: `python -m apps.worker.cli ingest --source=... --date=...`.
- Backtests triggered via API (POST `/api/v1/backtests`) or CLI.

---

# 7. Offline / Air-Gapped Install (§2.5 rules)

- `requirements.txt` mirrors to `offline_package/` wheels + `requirements-offline.txt`.
- Install: `pip install --no-index --find-links=./offline_package -r requirements-offline.txt`.
- Update `helper/resources.md` whenever dependencies change.

---

# 8. Production Hardening (future, §52)

- Load balancer + multiple FastAPI replicas; task queue (Redis/Celery or worker set) in front of workers.
- PostgreSQL/TimescaleDB managed service or dedicated VM with WAL backup + DR plan.
- Prometheus/Grafana; alert rules per §46.
- CI/CD (GitHub Actions/GitLab CI, or approved alternative): lint → test → build → image push → deploy.
- Cost monitoring for LLM spend per agent/model (§47).