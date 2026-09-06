# BACKTESTING

## AI Investment Research & Decision Intelligence Platform

**Version:** 1.0
**Status:** Baseline — derived from SYSTEM_SPECIFICATION.md v1.0 (§16, §17)

---

# 1. Role

Backtesting is a **first-class infrastructure component** (ADR-007), not a post-hoc add-on.

> A strategy/model is not production-ready until validated on appropriate historical data (§4.5).
> "Không có bước này thì không cho phép hệ thống tự tin đưa ra signal." (AI powered Investment.md, STEP 6)

---

# 2. Pipeline (§16)

```text
Historical Data
      ↓
Feature Generation      (as-of replay — no look-ahead)
      ↓
Signal Generation
      ↓
Portfolio Construction  (universe rules, position sizing, weights)
      ↓
Execution Simulation    (entry/exit on next bar, fill logic)
      ↓
Transaction Cost        (commission + spread + slippage, bps)
      ↓
Performance             (metrics §3 below)
```

---

# 3. Performance Metrics (§15 investment metrics)

```text
CAGR
Sharpe
Sortino
Calmar
Maximum Drawdown
Win Rate
Profit Factor
Turnover
Transaction Cost
```

Stored in `backtest_metrics` per run. **Never evaluate a model on prediction accuracy alone** (§15).

---

# 4. Bias Prevention (§17)

| Bias | Countermeasure |
|---|---|
| Look-ahead | as-of data replay with bitemporal `valid_from/valid_to` (financials), and features computed only from data available at `t` |
| Survivorship | historical universe from `listed_date/delisted_date`, delisted stocks retained |
| Data leakage | strict train/validation/test + walk-forward; no future info in features |
| Overfitting | in-sample / out-of-sample / walk-forward / rolling window evaluation; parameter sensitivity analysis |

Additional controls: transaction costs, slippage, corporate actions (splits/dividends via `adjusted_prices`).

---

# 5. Modes (§16)

| Mode | Meaning |
|---|---|
| In-sample | train & test on same window (baseline only) |
| Out-of-sample | untouched holdout |
| Walk-forward | rolling train → forward test, repeated |
| Rolling window | moving windows with fixed size |

Run types stored in `backtests.run_type`.

---

# 6. Execution Simulation

- Signals produced on day `t` using close-of-`t` data → trades execute at `t+1` open (avoids look-ahead).
- Transaction costs: `commission_bps + slippage_bps` recorded on `backtests` (configurable per run).
- Corporate actions applied via adjusted prices so returns are continuous.

---

# 7. Storage Model

See `docs/DATABASE_SCHEMA.md` §11:

- `backtests` — run definition + params + costs
- `backtest_trades` — every entry/exit with prices, quantity, PnL
- `backtest_metrics` — metric name/value pairs

---

# 8. Guardrail for Deployment

A strategy qualifies for a **signal** only after:

```text
passes data-quality gate (§39)   AND
passes walk-forward out-of-sample tests   AND
positive risk-adjusted metrics after costs   AND
documented sensitivity to parameters
```

Otherwise it remains `EXPERIMENTAL` and is never surfaced as a production signal.