# QUANT ENGINE

## AI Investment Research & Decision Intelligence Platform

**Version:** 1.0
**Status:** Baseline — derived from SYSTEM_SPECIFICATION.md v1.0 (§11, §12, §13)

---

# 1. Mandate

The Quant Engine is **fully deterministic** and operates **without any LLM involvement** (§4.2, §11).

- Every calculation is pure Python + NumPy/Pandas.
- Every formula is unit-tested against **expected values** (§38).
- LLM is never used for: RSI, MA, P/E, return, volatility, ranking, etc. (§47 cost control).

---

# 2. Factor Modules

## 2.1. Technical (§11.1) — `src/market/technical/`

| Indicator | Notes |
|---|---|
| SMA / EMA | configurable periods |
| RSI (14) | Wilder's smoothing |
| MACD | 12/26/9 |
| Bollinger Bands | 20, 2σ |
| ATR | 14 |
| ADX | 14 |
| Volume indicators | OBV, volume SMA / expansion |
| Relative strength | vs index & vs universe percentile |

## 2.2. Fundamental (§11.2) — `src/market/fundamental/`

| Ratio | Definition |
|---|---|
| Revenue growth | YoY from `financial_statements` |
| EPS growth | YoY |
| ROE | net profit / equity |
| ROA | net profit / assets |
| Margin | gross / operating / net |
| Debt | D/E, interest coverage |
| Cash flow | OCF, FCF, FCF margin |
| Quality | earnings quality composite (accruals proxy) |

## 2.3. Valuation (§11.3) — `src/market/valuation/`

Compare company vs industry vs historical valuation (§11.3):

- P/E, Forward P/E, P/B, EV/EBITDA, EV/Sales, Dividend Yield, PEG → `valuation_daily`
- Percentile within industry + percentile vs own 5-y history → contribution to `valuation_score`

## 2.4. Momentum (§11.4) — `src/market/momentum/`

- 5D / 20D / 60D / 120D returns
- Relative strength (vs VNINDEX, vs universe)
- Volume expansion

## 2.5. Risk (§11.5) — `src/market/risk/`

- Volatility (annualized, EWMA)
- Beta (universe index)
- Maximum drawdown (trailing)
- Liquidity (avg value traded pro-rata ADV/float)
- Gap risk (open-gap frequency)
- Earnings risk (report-date implied move)
- Debt risk (D/E level)

---

# 3. Score Pipeline (per stock per day)

```text
features (raw indicator values)
   ↓ filter by data quality gate (§39)
factor percentile ranks within universe / industry / history
   ↓
technical_score   (0-100)
fundamental_score (0-100)
valuation_score   (0-100)
momentum_score    (0-100)
quality_score     (0-100)
risk_score        (0-100)
   ↓
overall_score = Fundamental×0.30 + Technical×0.20 + Momentum×0.15
              + Valuation×0.15 + Quality×0.10 + Risk×0.10      (§12 baseline)
   ↓
persist to factor_scores with scoring_version
```

> **Warning (spec §12):** baseline weights are assumptions to be validated/re-learned by backtesting — never assumed optimal.

---

# 4. Score Normalization Rules

- Scores are bounded **0–100**.
- Percentile rank within the **current universe** (MVP: VN30), so scores are relative, not absolute.
- `market_regime` (from Market Regime Engine §13) is stored alongside each score as a **contextual feature** — it can modulate ranking/ML features, not the raw scores themselves.
- Every score must keep a **decomposition trail** for explainability (§43): overall → factor scores → sub-indicators.

---

# 5. Market Regime Engine (§13)

Inputs: VNINDEX trend, market breadth, volume, volatility (VIX-style), foreign flow, interest rates, liquidity, sector rotation.

Output: `{ "regime": "BULL|SIDEWAYS|BEAR|HIGH_VOLATILITY|CRISIS", "confidence": 0..1 }` persisted in `market_regimes`.

Used as a contextual feature for: stock ranking, ML prediction, portfolio construction, risk assessment.

---

# 6. Scoring Weights (Baseline)

```text
Fundamental      30%
Technical        20%
Momentum         15%
Valuation        15%
Quality          10%
Risk             10%
```

Versioned as `scoring_version = baseline_1.0`. Alternative weight sets are new versions, testable side-by-side via backtest.

---

# 7. Explainability (§43)

Every score persists enough decomposition to drill down:

```text
FPT Overall Score: 86
  Fundamental: 92  → Revenue Growth | EPS Growth | ROE | Margin | FCF | Debt
  Technical:   84  → RSI | MACD | Trend | Volume
  Momentum:    88  → 5D / 20D / 60D / 120D | Relative Strength
  Valuation:   76  → P/E vs Industry | P/B | EV/EBITDA
  Quality:     91  → ...
  Risk:        73  → Volatility | Beta | MaxDD | Liquidity
```

Decomposition contract (`src/quant/scoring/engine.py`): when a factor score is missing the remaining
weights are **renormalized**, and every reported contribution uses its renormalized weight, so
`Σ weighted_score == overall_score` and `Σ contribution_pct == 1` (shares add up to 100% of the
score). `weight` is therefore the *applied* weight, not the raw `scoring_weights.yaml` baseline.

---

# 8. Testing Requirements (§38)

- Indicator formulas validated against hand-computed expected values.
- Score pipeline tested for: bounds (0–100), monotonicity of sorting, weighting math, empty/NaN handling, minimal-data edge cases (30 bars).
- Regression tests pinned to committed fixture datasets.