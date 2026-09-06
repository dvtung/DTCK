# DATA ARCHITECTURE

## AI Investment Research & Decision Intelligence Platform

**Version:** 1.0
**Status:** Baseline — derived from SYSTEM_SPECIFICATION.md v1.0 (§9, §10)

---

# 1. Data Domains (§10)

| Domain | Tables (PostgreSQL) | Qdrant | Notes |
|---|---|---|---|
| Market Data | `prices`, `adjusted_prices`, `index_prices`, `foreign_flows`, `prop_trading_flows` | — | EOD OHLCV, value, mcap, foreign/prop flows |
| Fundamental | `financial_statements`, `financial_ratios` | — | bitemporal statements (restatements), precomputed ratios |
| Valuation | `valuation_daily` | — | P/E, P/B, EV/EBITDA, EV/Sales, DY, PEG per day |
| Technical | `features` | — | SMA, EMA, RSI, MACD, Bollinger, ATR, ADX… |
| Macro | `macro_indicators` | — | GDP, CPI, rates, FX, credit growth, M2 |
| Corporate Events | `corporate_events` | payloads embeddable | earnings, dividends, splits, rights, AGM, M&A, legal |
| News | `news`, `news_symbols` | full item + embedding | title, content, sentiment, importance, symbol links |
| Signals | `signals` | — | deterministic, versioned |
| Features | `features` | — | feature store (0..n per stock/day), feature_versioned |

---

# 2. Data Ingestion Pipeline (STEP 3 of spec §57)

```text
Source
  ↓
Collector        → fetch, paginate, rate-limit, auth
  ↓
Validator        → schema check, nulls, ranges, uniqueness, monotonicity, source freshness
  ↓
Normalizer       → symbol/exchange mapping, currency, adjustment factors, dedup
  ↓
PostgreSQL       → idempotent upsert (ON CONFLICT DO UPDATE where source allows)
```

- Runs in **worker** app via APScheduler (EOD jobs; intraday later).
- Each batch records provenance: `source`, `ingested_at`, batch id.
- **Retry + error handling + alerting** per §8.1.

---

# 3. Data Quality Framework (§39)

Every dataset scored 0–100 on six dimensions into `data_quality_scores`:

| Dimension | Definition | Example check |
|---|---|---|
| Completeness | % of expected rows present | trading days x universe |
| Accuracy | error vs trusted benchmark | compare OHLC against exchange feed |
| Consistency | internal cross-field coherence | high ≥ low ≥ close/open bounds |
| Freshness | age of latest data vs expectation | last trade_date == last session |
| Uniqueness | duplicate ratio | (stock_id, trade_date) duplicates |
| Validity | domain/constraint violations | price > 0, volume ≥ 0 |

**Gate:** if `overall_score < threshold` → mark `below_threshold = true` → the dataset is **not used for prediction/backtest** (§39). Preserve raw data for re-processing; never silently drop.

---

# 4. Market Data Handling

- `prices` stores **raw** OHLCV exactly as received (source, ingested_at preserved).
- `adjusted_prices` stores `adj_factor`, `adj_close` computed via corporate action feed — raw never mutated (§4.1, §4.2 design principles).
- `index_prices` for VNINDEX / VN30 / HNX / UPCOM indexes — used by Market Regime Engine (§13).
- **Survivorship bias control (§17):** delisted stocks stay in `stocks` with `status='DELISTED'`; historical universe reconstruction uses `listed_date`/`delisted_date`.

---

# 5. Financial Statement Bitemporality (§5.1 DATABASE_SCHEMA)

- `valid_from`/`valid_to` window per (statement, line_item).
- Any consumer must query as-of: `valid_from <= as_of < COALESCE(valid_to, 'infinity')`.
- This is mandatory for the backtester — prevents look-ahead bias from restatements (§17).

---

# 6. Signals & Features Versioning

| Concept | Field | Convention |
|---|---|---|
| Data version | `source` + `ingested_at` | per-batch |
| Feature version | `feature_version` | bump on any calc change (e.g. `technical_1.0`) |
| Scoring version | `scoring_version` | weight-set version (e.g. `baseline_1.0`) |
| Model version | `model_registry.version` | tied to training data + feature versions (§40) |

The invariant:

> A prediction must be reproducible given `(stock, trade_date, data_version, feature_version, model_id, model_version)`.

---

# 7. Storage Technologies Summary

| Store | Tech | Purpose |
|---|---|---|
| Relational/time-series | PostgreSQL + TimescaleDB | all structured data, hypertables (§17 DB schema) |
| Vector | Qdrant | document/news embeddings + metadata filters |
| Object (future) | S3-compatible | raw PDFs, backtest artifacts, snapshots (§9.3) |
| Cache (future) | Redis | optional API caching beyond MVP |

---

# 8. Migration & Seed Strategy

- **Alembic** migrations under `database/migrations/`; one logical change per migration; immutable once merged.
- TimescaleDB hypertable creation happens in the same migration immediately after table creation.
- Seeds in `database/seeds/`: exchanges (HOSE/HNX/UPCOM), sectors/industries taxonomy, VN30/VN100 membership snapshots.
- See `docs/DATABASE_SCHEMA.md` §18.