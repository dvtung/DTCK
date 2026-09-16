# Memory Bank — Active Task

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
