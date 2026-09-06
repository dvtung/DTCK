# ML ARCHITECTURE

## AI Investment Research & Decision Intelligence Platform

**Version:** 1.0
**Status:** Baseline — derived from SYSTEM_SPECIFICATION.md v1.0 (§14, §15, §26)

---

# 1. Mandate

- LLM is **not** the primary prediction engine (§14). Prediction is the job of classically-trained models.
- Initial tooling: **XGBoost, LightGBM, Scikit-learn**.
- Model can only be used after proper training/validation/calibration + registry registration (§40).

---

# 2. Problem Formulation

| Target | Type | Horizon |
|---|---|---|
| `P(return > 0)` | binary classification | declared per model |
| `P(return > 5%)` | binary classification | declared per model |
| `P(return > 10%)` | binary classification | declared per model |
| Expected return | regression | declared per model |
| Volatility / Drawdown | regression | declared per model |

Horizons supported (§6): SHORT (1–20 TD), MEDIUM (1–6 m), LONG (6–36 m).

Every prediction **must** declare its horizon — no time-frame-less predictions (§6).

---

# 3. Feature Dataset

```text
features (feature store, src/quant)      → X matrix
targets (forward returns w/ declared horizon) → y
metadata (trade_date, stock_id, regime)  → sample identity
```

- Feature versioning: `feature_version`; dataset versioning: `training_data_version`.
- Row-level as-of alignment prevents leakage (§17).
- Market regime stored as a contextual feature (§13).

---

# 4. Training & Validation

```text
Train → Validation → Test (temporal split, no shuffle across time)
   + out-of-sample holdout
   + walk-forward / rolling retrain
```

## 4.1. Metrics (§15)

Classification: Accuracy, Precision, Recall, F1, ROC-AUC, Log Loss, Brier Score, Calibration.

Investment: CAGR, Sharpe, Sortino, Calmar, MaxDD, Win Rate, Profit Factor, Turnover, Transaction Cost.

## 4.2. Calibration

Probability outputs must be calibrated (Platt/isotonic). A model whose probabilities are miscalibrated is not deployable — confidence drives agent behavior (§24).

---

# 5. Model Registry (§40)

`model_registry` requires: model_id, version, training data version, feature version, training/validation/test periods, metrics, parameters, owner, status.

Status lifecycle: `EXPERIMENTAL → VALIDATING → APPROVED → PRODUCTION → DEPRECATED`.

---

# 6. Prediction Storage & Evaluation (§26)

- `predictions` stores `(stock, trade_date, model_id, model_version, feature_version, target, predicted_value, horizon_days)`.
- After the horizon elapses, `prediction_evaluations` records the actual outcome, error, hit.
- Model performance is computed from evaluated predictions — closing the loop.

---

# 7. Reproducibility

```text
(stock, trade_date, data_version, feature_version, model_id, model_version)
   → reproducible prediction
```

Supported by immutable-ish versioning in every layer (see DATA_ARCHITECTURE.md §6).

---

# 8. Anti-Patterns

- ❌ Training/tuning on the test period.
- ❌ Categorical/ID features leaking future info (target leakage via post-hoc restatements).
- ❌ Using the LLM to generate features/numbers (§4.2, §47).
- ❌ Deploying an unregistered or `EXPERIMENTAL` model to production outputs.