# Memory Bank — Active Task

## Deployment fix — phase 2 `alembic upgrade head` (2026-09-18)

**State:** COMPLETED (repo fix) + 2 host/env blockers reported
**Goal:** make the documented phase-2 commands work inside the containers.
**Scope:** `docker/Dockerfile.api`, `docker/Dockerfile.worker`, `tests/unit/test_deployment_config.py`, deployment docs.

Root cause of the reported error: **`alembic.ini` was never copied into the images**
(only `pyproject.toml`/`README.md`/`src`/`apps`/`database` were), and Compose mounts
only `./src` + `./database` — so `alembic` ran with no config (`script_location` missing).

- [x] `COPY pyproject.toml README.md alembic.ini ./` in the API and worker images
      (dashboard stays minimal: it ships neither `database/` nor migrations, and the
      regression test enforces "alembic.ini  database/" for every image).
- [x] Rebuilt images; `/app/alembic.ini` + `/app/database/migrations/env.py` present.
- [x] In container: `alembic heads` → `0001_initial_schema (head)`, i.e. config now loads.
- [x] New regression test `tests/unit/test_deployment_config.py` (script_location exists,
      ini has no real credentials and `env.py` prefers `DATABASE_URL`, images that carry
      migrations also carry the config, documented runner can run alembic, alembic stays
      a core dependency).

**Blocker A (host, not repo):** containers cannot reach `db`/`qdrant` at all — api's 15
SYNs left api and arrived on api's host veth, but the db/qdrant host veth TX counters did
not move (frames dropped on the host), while host→container and container→api/worker/
dashboard work. Bridge ports identical (forwarding/flood/learning on, isolated off),
FDB correct, conntrack 139/262144, MACs verified, persistence across network + container
recreation, unaffected by IP reassignment. Needs root: `sudo iptables -S FORWARD`,
`sudo nft list ruleset | grep -i drop`, `sudo ebtables -L`, `sudo systemctl restart docker`.

**Blocker B (env, not repo) — RESOLVED 2026-09-18:** credential drift — DB volume created
2026-09-13, `.env` edited 2026-09-18; `POSTGRES_PASSWORD` is only honoured at first init,
so the role still had `change_me` (verified: `change_me` authenticated from the host while
the `.env` value did not). Per the user's decision, `.env` was restored to
`POSTGRES_PASSWORD=change_me` / matching `DATABASE_URL`; the stack was recreated so the
containers pick up the new value. Host-side phase-2 verification then passed end-to-end:
`alembic current` → `0001_initial_schema (head)`, `alembic upgrade head` → exit 0,
`python -m database.seeds.run_all` → 3 exchanges / 10 sectors / 15 industries / 30 VN30
(idempotent, exit 0), counts `39 tables | 12 hypertables | 30 stocks`.

Current DB state (unchanged by this task): revision `0001_initial_schema`, 39 tables
(38 + `alembic_version`), 12 hypertables, 30 VN30 constituents.

**Still open:** blocker A. In-container `alembic current` is killed by timeout (exit 143)
while `alembic heads` succeeds — the config is fine, only the `api → db` network path is
broken. Phase-2 steps can be run from the host until the host firewall is fixed.

## Previous task

## Deployment fix — missing sklearn (2026-09-17)

**State:** COMPLETED
**Goal:** API starts with reproducible ML dependencies in Docker; preserve public ML imports.
**Scope:** API/worker Dockerfiles, lazy ML package exports, regression tests and deployment docs.
**Constraints:** Preserve existing Compose edits and database volumes; use existing `[ml]` extra.

- [x] Build API/worker images: `BUILD_EXIT_CODE=0`.
- [x] Recreate only API/worker with `docker compose up -d --no-deps api worker`.
- [x] API imports sklearn 1.9.1, xgboost 2.1.4, lightgbm 4.7.0; worker imports ModelTrainer.
- [x] Container `/healthz` and `/api/v1/predictions/VNM` return HTTP 200.
- [x] Lint, types and unit regression tests (including blocked optional ML imports).
  - `ruff check .` clean · `mypy src apps` clean (119 files) · `pytest tests/unit` **343 passed, 1 skipped**
    (run with `LLM_PROVIDER=mock`; local `.env` sets `ollama`, which the smoke-test allowlist rejects)
  - In-container: `import sklearn` → 1.9.1; blocked-import smoke proves `apps.api.main`
    imports without sklearn and `src.ml.training` stays lazy.

## Previous task


**ID:** `T014 — ML prediction: feature dataset + training + calibration + registry + predictions API (Phase 6)`
**State:** COMPLETED (2026-09-16)

**Goal:** Classically-trained prediction per spec §14/§15/§26/§40 + `docs/ML_ARCHITECTURE.md`: as-of feature dataset (no leakage), XGBoost training with temporal splits, Platt-style calibration, versioned model registry with status lifecycle, `/api/v1/predictions` endpoints, worker `train-model` CLI.

**Scope:** `src/ml/` (feature_dataset, training, model_registry, predictor, schemas), `apps/api/routers/predictions.py`, `apps/worker/cli.py` (train-model), `tests/unit/test_ml_*.py`, `test_t014_t015.py`.

**Constraints:** Deterministic offline-first; sklearn 1.8+ compatible (no `CalibratedClassifierCV cv="prefit"`); no target leakage in features.

**Key fixes during implementation:**
- **Target leakage removed:** `horizon_return_*` forward-return columns were in the feature matrix (`horizon_return_5d` == target exactly); deleted from features, kept only in targets. Regression tests prove features are invariant to future price shocks.
- **Duplicate-date split bug:** temporal split used row counts; a date could land in two partitions. Now splits on unique trade dates; guards reject single-class partitions, misaligned frames, and non-0/1 labels.
- **`hash()` symbol feature** was process-randomized (PYTHONHASHSEED) → replaced with `zlib.crc32`.
- **KI-012 (new):** the synthetic market fixture is monotonically rising → 100% positive 5-day labels; a real classifier cannot be fit. `train()`/`train-model` fail loudly instead of emitting a fake model; predictor serves a deterministic fallback stub. Real training is blocked on DB wiring (KI-006/007/008).

**Acceptance:**
- [x] `ruff check .` clean
- [x] `mypy` clean — "Success: no issues found in 119 source files"
- [x] `pytest -q` — **325 passed** (+12 ML/API tests; leakage + training contract)
- [x] `docs/htmldocs/status.html` updated (ML 80%, KI-012, roadmap → T015)
- [x] memory-bank updated (active-task/current-state/changelog/tasks)
