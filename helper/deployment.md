# Deployment Guide (helpers)

## AI Investment Research & Decision Intelligence Platform

Main deployment doc: `docs/DEPLOYMENT.md`.

> **🇻🇳 Hướng dẫn triển khai chi tiết từng bước bằng tiếng Việt: [`docs/DEPLOYMENT_vi.md`](../docs/DEPLOYMENT_vi.md)** — gồm 6 giai đoạn (chuẩn bị → hạ tầng → migration/seed → dữ liệu → kiểm thử → vận hành) + troubleshooting.

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

### `alembic upgrade head` fails with `No 'script_location' key found in configuration`

The repo-root `alembic.ini` (`script_location = database/migrations`) is baked into
the API and worker images next to the migration scripts, so it resolves against the
image `WORKDIR` (/app). If the image predates that fix, rebuild it:

```bash
docker compose build api worker
docker compose up -d --no-deps api worker
docker compose exec -T api alembic current      # -> 0001_initial_schema (head)
```

### `FATAL: password authentication failed for user "dtck"`

`POSTGRES_PASSWORD` is only read when the data volume is initialised, so changing it
in `.env` afterwards leaves the database role with the old password. Either restore
the previous value in `.env` or align the role:

```bash
docker compose exec -T db psql -U dtck -d dtck -c "ALTER USER dtck WITH PASSWORD '<password-from-.env>'"
```

`docker compose down -v` also resets it but destroys all data.

### Containers cannot reach `db` / `qdrant` (timeouts, not auth errors)

This is host-level networking, not application config. Confirm the drop is on the
host bridge (`docker compose exec -T api python3 -c "import socket; socket.create_connection(('db', 5432), 5)"`)
then inspect the host firewall with root privileges:

```bash
sudo iptables -S FORWARD | head -40
sudo nft list ruleset | grep -i -E 'drop|reject' | head -20
sudo ebtables -L | head -20
sudo systemctl restart docker      # recreates bridges + iptables rules
```

### API fails with `ModuleNotFoundError: No module named 'sklearn'`

API and worker images install the existing `.[dev,ml]` extra. `sklearn` is
provided by the `scikit-learn` package. The ML package also loads training exports
lazily so API startup does not require the optional training stack.

After updating the Dockerfiles, rebuild and recreate (restart alone is insufficient):

```bash
docker compose build api worker
docker compose up -d --no-deps api worker
docker compose exec -T api python -c "import sklearn, xgboost, lightgbm; print(sklearn.__version__)"
docker compose exec -T api curl --fail http://localhost:8000/healthz
```

These commands preserve database volumes. ML packages increase image size and
build time; no new environment variables are needed.



- **Port conflicts:** change `POSTGRES_PORT`, `API_PORT` etc. in `.env`.
- **TimescaleDB not ready:** worker/api depend_on healthcheck; wait for `pg_isready`.
- **Offline install:** `pip install --no-index --find-links=./offline_package -r requirements-offline.txt`.
- Local Python is 3.14 — prefer Docker for reproducibility (pinned images).