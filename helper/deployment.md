# Deployment Guide (helpers)

## AI Investment Research & Decision Intelligence Platform

Main deployment doc: `docs/DEPLOYMENT.md`.

---

## Local Setup (MVP)

```bash
# From repo root
cp .env.example .env        # fill real values, never commit .env

docker compose up --build -d          # api + worker + timescaledb + qdrant + dashboard
docker compose exec api alembic upgrade head
docker compose exec api python -m database.seeds.run_all
docker compose ps
```

Endpoints:
- API docs: http://localhost:8000/docs
- Dashboard: http://localhost:8501
- Qdrant: http://localhost:6333/dashboard

## Common commands

```bash
docker compose logs -f api            # follow API logs
docker compose exec api pytest        # run tests inside container
docker compose down                   # stop (keeps volumes)
docker compose down -v                # WIPEOUT volumes (destructive — data loss!)
```

## Environment variables

See `.env.example` — never commit real secrets.

## Known issues / troubleshooting

- **Port conflicts:** change `POSTGRES_PORT`, `API_PORT` etc. in `.env`.
- **TimescaleDB not ready:** worker/api depend_on healthcheck; wait for `pg_isready`.
- **Offline install:** `pip install --no-index --find-links=./offline_package -r requirements-offline.txt`.
- Local Python is 3.14 — prefer Docker for reproducibility (pinned images).