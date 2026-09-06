# DATABASE SCHEMA

## AI Investment Research & Decision Intelligence Platform

**Version:** 1.0
**Status:** Draft — derived from SYSTEM_SPECIFICATION.md v1.0
**Primary Store:** PostgreSQL + TimescaleDB extension
**Vector Store:** Qdrant (see RAG_ARCHITECTURE.md — not covered here)

---

# 1. Design Principles

1. Every table that carries time-series market/quant data must be a **TimescaleDB hypertable** partitioned on its timestamp column.
2. Every derived value (feature, score, signal, prediction) must be traceable to a `data_version` / `feature_version` / `model_version`.
3. No table may allow **retroactive mutation of historical facts** used in features already computed (append-only where possible; corrections are new rows, not UPDATEs, except for explicit `is_latest` correction flows).
4. Every table has `created_at timestamptz` and, where mutable, `updated_at timestamptz`.
5. Symbols are the natural join key: `symbol` (ticker) + `exchange` uniquely identifies a listed instrument over time (handles delisting/relisting via `stocks` history).
6. Foreign keys enforced at the database level. Soft business validity (bitemporal effective dating) handled via `valid_from` / `valid_to` on slowly-changing tables (e.g. `financial_statements` restatements).

---

# 2. Schema Overview (Domains → Tables)

```text
Reference        : stocks, exchanges, sectors, industries
Market Data       : prices, adjusted_prices, index_prices, foreign_flows, prop_trading_flows
Fundamental Data  : financial_statements, financial_ratios
Corporate Events  : corporate_events
News              : news, news_symbols
Macro Data        : macro_indicators
Quant             : features, factor_scores, signals, market_regimes
ML                : ml_models, predictions, prediction_evaluations
Backtesting       : backtests, backtest_trades, backtest_metrics
RAG / Evidence    : documents (metadata only; vectors live in Qdrant), evidence
Agents            : agent_runs, agent_tool_calls
Portfolio         : portfolios, portfolio_positions, portfolio_snapshots
Governance/Audit  : model_registry, agent_registry, audit_logs, data_quality_scores
Users/Auth        : users, api_keys, roles
```

---

# 3. Reference Tables

## 3.1. `exchanges`

| Column | Type | Notes |
|---|---|---|
| id | smallserial PK | |
| code | text UNIQUE | `HOSE`, `HNX`, `UPCOM` |
| name | text | |

## 3.2. `sectors` / `industries`

| Column | Type | Notes |
|---|---|---|
| id | serial PK | |
| code | text UNIQUE | ICB or custom taxonomy code |
| name | text | |
| parent_id | int FK → sectors.id | nullable, for industry → sector rollup |

## 3.3. `stocks`

| Column | Type | Notes |
|---|---|---|
| id | serial PK | |
| symbol | text | e.g. `FPT` |
| exchange_id | smallint FK → exchanges.id | |
| company_name | text | |
| sector_id | int FK → sectors.id | |
| industry_id | int FK → industries.id | |
| listed_date | date | |
| delisted_date | date | nullable |
| status | text | `ACTIVE`, `DELISTED`, `SUSPENDED` |
| is_vn30 | boolean | flag for MVP universe |
| is_vn100 | boolean | |
| created_at | timestamptz | |
| updated_at | timestamptz | |

`UNIQUE (symbol, exchange_id)`. Delisted stocks are **kept** (never deleted) to prevent survivorship bias (§17 spec).

---

# 4. Market Data (TimescaleDB Hypertables)

## 4.1. `prices` (raw OHLCV, hypertable on `trade_date`)

| Column | Type | Notes |
|---|---|---|
| stock_id | int FK → stocks.id | |
| trade_date | date | partition key |
| open | numeric(18,4) | |
| high | numeric(18,4) | |
| low | numeric(18,4) | |
| close | numeric(18,4) | |
| volume | bigint | |
| trading_value | numeric(20,2) | |
| source | text | data provenance |
| ingested_at | timestamptz | |

`PRIMARY KEY (stock_id, trade_date)`. Hypertable partitioned by `trade_date` (1-month chunks).

## 4.2. `adjusted_prices`

Same shape as `prices` plus:

| Column | Type | Notes |
|---|---|---|
| adj_factor | numeric(18,8) | cumulative adjustment for splits/dividends |
| adj_close | numeric(18,4) | |

Kept separate from raw `prices` so raw source data is never mutated (§4.1 Data First principle).

## 4.3. `index_prices`

| Column | Type | Notes |
|---|---|---|
| index_code | text | `VNINDEX`, `VN30`, `HNXINDEX`, `UPCOMINDEX` |
| trade_date | date | |
| open/high/low/close | numeric | |
| volume | bigint | |
| trading_value | numeric(20,2) | |

`PRIMARY KEY (index_code, trade_date)`, hypertable.

## 4.4. `foreign_flows`

| Column | Type | Notes |
|---|---|---|
| stock_id | int FK | |
| trade_date | date | |
| foreign_buy_value | numeric(20,2) | |
| foreign_sell_value | numeric(20,2) | |
| foreign_net_value | numeric(20,2) | generated column `foreign_buy_value - foreign_sell_value` |
| foreign_room_pct | numeric(6,3) | remaining foreign ownership room |

`PRIMARY KEY (stock_id, trade_date)`, hypertable.

## 4.5. `prop_trading_flows`

| Column | Type | Notes |
|---|---|---|
| stock_id | int FK | |
| trade_date | date | |
| prop_buy_value | numeric(20,2) | |
| prop_sell_value | numeric(20,2) | |

`PRIMARY KEY (stock_id, trade_date)`, hypertable.

---

# 5. Fundamental Data

## 5.1. `financial_statements`

Bitemporal because financials get restated.

| Column | Type | Notes |
|---|---|---|
| id | bigserial PK | |
| stock_id | int FK | |
| period_type | text | `QUARTER`, `YEAR` |
| fiscal_year | smallint | |
| fiscal_period | smallint | 1-4 for quarter, 0 for year |
| statement_type | text | `INCOME`, `BALANCE`, `CASHFLOW` |
| line_item | text | e.g. `revenue`, `net_profit`, `total_assets` |
| value | numeric(24,4) | |
| currency | text | default `VND` |
| report_date | date | when statement was filed |
| valid_from | timestamptz | bitemporal validity start |
| valid_to | timestamptz | null = current |
| source | text | |
| created_at | timestamptz | |

`UNIQUE (stock_id, period_type, fiscal_year, fiscal_period, statement_type, line_item, valid_from)`. Querying "as-of" a historical date requires filtering `valid_from <= as_of < COALESCE(valid_to, 'infinity')` — this is what prevents **look-ahead bias** when the backtester replays history (§17).

## 5.2. `financial_ratios`

Precomputed deterministic ratios (never LLM-generated, per §4.2).

| Column | Type | Notes |
|---|---|---|
| id | bigserial PK | |
| stock_id | int FK | |
| period_type | text | |
| fiscal_year | smallint | |
| fiscal_period | smallint | |
| ratio_name | text | `ROE`, `ROA`, `EPS`, `revenue_growth_yoy`, `debt_to_equity`, ... |
| value | numeric(18,6) | |
| calculated_at | timestamptz | |
| calc_version | text | version of the calculation engine that produced it |

`UNIQUE (stock_id, period_type, fiscal_year, fiscal_period, ratio_name, calc_version)`.

---

# 6. Valuation Snapshot

## 6.1. `valuation_daily` (hypertable)

| Column | Type | Notes |
|---|---|---|
| stock_id | int FK | |
| trade_date | date | |
| pe | numeric(12,4) | |
| forward_pe | numeric(12,4) | |
| pb | numeric(12,4) | |
| ev_ebitda | numeric(12,4) | |
| ev_sales | numeric(12,4) | |
| dividend_yield | numeric(8,4) | |
| peg | numeric(12,4) | |
| industry_pe_median | numeric(12,4) | for peer comparison (§11.3) |

`PRIMARY KEY (stock_id, trade_date)`, hypertable.

---

# 7. Corporate Events & News

## 7.1. `corporate_events`

| Column | Type | Notes |
|---|---|---|
| id | bigserial PK | |
| stock_id | int FK | |
| event_type | text | `EARNINGS`, `DIVIDEND`, `SPLIT`, `RIGHTS_ISSUE`, `AGM`, `MANAGEMENT_CHANGE`, `M&A`, `LEGAL`, `CAPITAL_INCREASE` |
| event_date | date | |
| announced_date | date | |
| details | jsonb | structured payload specific to event_type |
| source | text | |
| created_at | timestamptz | |

## 7.2. `news`

Metadata table; full text is embedded and stored in Qdrant, but the metadata + text stay here for BM25/keyword search and provenance.

| Column | Type | Notes |
|---|---|---|
| id | bigserial PK | |
| source | text | |
| title | text | |
| content | text | |
| published_at | timestamptz | |
| sector_id | int FK | nullable |
| event_type | text | nullable |
| sentiment | numeric(4,3) | -1..1 |
| importance | numeric(4,3) | 0..1 |
| qdrant_point_id | uuid | pointer to vector store |
| ingested_at | timestamptz | |

## 7.3. `news_symbols` (many-to-many)

| Column | Type | Notes |
|---|---|---|
| news_id | bigint FK → news.id | |
| stock_id | int FK → stocks.id | |

`PRIMARY KEY (news_id, stock_id)`.

---

# 8. Macro Data

## 8.1. `macro_indicators` (hypertable)

| Column | Type | Notes |
|---|---|---|
| indicator_code | text | `GDP`, `CPI`, `INTEREST_RATE`, `FX_USDVND`, `CREDIT_GROWTH`, `M2` |
| period_date | date | |
| value | numeric(24,6) | |
| unit | text | |
| source | text | |

`PRIMARY KEY (indicator_code, period_date)`, hypertable.
---

# 9. Quant Engine Outputs

## 9.1. `features` (hypertable) — generic feature store

| Column | Type | Notes |
|---|---|---|
| stock_id | int FK | |
| trade_date | date | |
| feature_name | text | e.g. `rsi_14`, `macd`, `sma_50`, `momentum_20d` |
| value | numeric(24,8) | |
| feature_version | text | |
| calculated_at | timestamptz | |

`PRIMARY KEY (stock_id, trade_date, feature_name, feature_version)`, hypertable.

## 9.2. `factor_scores` (hypertable)

| Column | Type | Notes |
|---|---|---|
| stock_id | int FK | |
| trade_date | date | |
| technical_score | numeric(6,2) | 0-100 |
| fundamental_score | numeric(6,2) | 0-100 |
| valuation_score | numeric(6,2) | 0-100 |
| momentum_score | numeric(6,2) | 0-100 |
| quality_score | numeric(6,2) | 0-100 |
| risk_score | numeric(6,2) | 0-100 |
| overall_score | numeric(6,2) | weighted (§12) |
| scoring_version | text | weight set version, e.g. `baseline_1.0` |
| market_regime | text | contextual feature at scoring time (§13) |

`PRIMARY KEY (stock_id, trade_date, scoring_version)`, hypertable.

## 9.3. `signals` (hypertable)

| Column | Type | Notes |
|---|---|---|
| id | bigserial PK | |
| stock_id | int FK | |
| trade_date | date | |
| signal_type | text | `TECHNICAL`, `FUNDAMENTAL`, `RISK`, `COMPOSITE` |
| signal_value | text | e.g. `POSITIVE`, `NEGATIVE`, `NEUTRAL` |
| strength | numeric(6,3) | |
| horizon | text | `SHORT`, `MEDIUM`, `LONG` |
| generated_by | text | engine/model identifier |

## 9.4. `market_regimes` (hypertable)

| Column | Type | Notes |
|---|---|---|
| trade_date | date PK | |
| regime | text | `BULL`, `SIDEWAYS`, `BEAR`, `HIGH_VOLATILITY`, `CRISIS` |
| confidence | numeric(5,4) | |
| inputs | jsonb | snapshot of contributing signals (breadth, volume, volatility, foreign flow) |

---

# 10. Machine Learning

## 10.1. `model_registry` (§40 Model Governance)

| Column | Type | Notes |
|---|---|---|
| model_id | text PK | e.g. `xgb_return20d` |
| version | text | part of composite key below |
| training_data_version | text | |
| feature_version | text | |
| training_period_start | date | |
| training_period_end | date | |
| validation_period_start | date | |
| validation_period_end | date | |
| test_period_start | date | |
| test_period_end | date | |
| metrics | jsonb | accuracy, AUC, log-loss, Brier, calibration, CAGR, Sharpe... (§15) |
| parameters | jsonb | hyperparameters |
| owner | text | |
| status | text | `EXPERIMENTAL`, `VALIDATING`, `APPROVED`, `PRODUCTION`, `DEPRECATED` (§40) |
| created_at | timestamptz | |

`PRIMARY KEY (model_id, version)`.

## 10.2. `predictions` (hypertable)

| Column | Type | Notes |
|---|---|---|
| id | bigserial PK | |
| stock_id | int FK | |
| trade_date | date | as-of date of prediction |
| model_id | text | |
| model_version | text | FK → model_registry |
| feature_version | text | |
| target | text | e.g. `P(return>5%)`, `expected_return`, `volatility` |
| predicted_value | numeric(18,8) | |
| horizon_days | int | |
| created_at | timestamptz | |

## 10.3. `prediction_evaluations` (§26 Prediction Tracking)

| Column | Type | Notes |
|---|---|---|
| prediction_id | bigint FK → predictions.id | |
| actual_value | numeric(18,8) | |
| evaluated_at | timestamptz | |
| error | numeric(18,8) | |
| hit | boolean | for classification-style targets |

`PRIMARY KEY (prediction_id)`.
---

# 11. Backtesting

## 11.1. `backtests`

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| strategy_name | text | |
| strategy_version | text | |
| universe | text | e.g. `VN30` |
| start_date | date | |
| end_date | date | |
| params | jsonb | |
| transaction_cost_bps | numeric(8,3) | |
| slippage_bps | numeric(8,3) | |
| run_type | text | `IN_SAMPLE`, `OUT_OF_SAMPLE`, `WALK_FORWARD`, `ROLLING` |
| created_at | timestamptz | |

## 11.2. `backtest_trades`

| Column | Type | Notes |
|---|---|---|
| id | bigserial PK | |
| backtest_id | uuid FK | |
| stock_id | int FK | |
| entry_date | date | |
| exit_date | date | |
| entry_price | numeric(18,4) | |
| exit_price | numeric(18,4) | |
| quantity | numeric(18,4) | |
| pnl | numeric(20,4) | |
| return_pct | numeric(10,6) | |

## 11.3. `backtest_metrics` (§16 Backtesting Engine)

| Column | Type | Notes |
|---|---|---|
| backtest_id | uuid FK | |
| metric_name | text | `CAGR`, `Sharpe`, `Sortino`, `Calmar`, `MaxDrawdown`, `WinRate`, `ProfitFactor`, `Turnover`, `TransactionCost` |
| value | numeric(20,8) | |

`PRIMARY KEY (backtest_id, metric_name)`.

---

# 12. RAG / Evidence

## 12.1. `documents`

Metadata for anything embedded into Qdrant (annual reports, quarterly reports, disclosures, research docs).

| Column | Type | Notes |
|---|---|---|
| id | bigserial PK | |
| stock_id | int FK | nullable (some docs are macro/sector-level) |
| doc_type | text | `ANNUAL_REPORT`, `QUARTERLY_REPORT`, `DISCLOSURE`, `RESEARCH`, `NEWS` |
| title | text | |
| published_at | timestamptz | |
| source | text | |
| storage_path | text | object storage path (future) |
| qdrant_point_id | uuid | |
| created_at | timestamptz | |

## 12.2. `evidence` (§19 Evidence Engine)

| Column | Type | Notes |
|---|---|---|
| id | bigserial PK | |
| claim | text | |
| source | text | |
| source_type | text | `financial_report`, `news`, `filing`, ... |
| published_at | timestamptz | |
| data_timestamp | timestamptz | as-of time of underlying data |
| evidence_text | text | |
| confidence | numeric(5,4) | |
| linked_entity_type | text | `ANALYSIS`, `PREDICTION`, `AGENT_RUN`, `REPORT` |
| linked_entity_id | text | polymorphic FK (id of the linked_entity_type row) |
| created_at | timestamptz | |
---

# 13. Agents (§20 / §41 Agent Governance)

## 13.1. `agent_registry`

| Column | Type | Notes |
|---|---|---|
| agent_id | text PK | `research`, `analysis`, `monitoring`, `portfolio`, `orchestrator` |
| version | text | |
| system_prompt_version | text | |
| available_tools | jsonb | list of tool names |
| allowed_data | jsonb | scoping rules |
| output_schema_ref | text | pydantic model name/version |
| evaluation_score | numeric(6,3) | |
| status | text | |

`PRIMARY KEY (agent_id, version)`.

## 13.2. `agent_runs` (§31 Audit System)

| Column | Type | Notes |
|---|---|---|
| agent_run_id | uuid PK | |
| user_request | text | |
| agent_id | text | |
| agent_version | text | |
| model | text | LLM provider/model name |
| model_version | text | |
| prompt_version | text | |
| final_output | jsonb | structured agent output (§23) |
| confidence | numeric(5,4) | |
| status | text | `SUCCESS`, `FAILED`, `TIMEOUT` |
| started_at | timestamptz | |
| finished_at | timestamptz | |
| latency_ms | int | |
| token_usage | jsonb | prompt/completion tokens, cost |

## 13.3. `agent_tool_calls` (§22 Tool Architecture)

| Column | Type | Notes |
|---|---|---|
| id | bigserial PK | |
| agent_run_id | uuid FK → agent_runs.agent_run_id | |
| tool_name | text | |
| tool_input | jsonb | |
| tool_output | jsonb | |
| called_at | timestamptz | |
| latency_ms | int | |

---

# 14. Portfolio

## 14.1. `portfolios`

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| name | text | |
| owner | text | |
| created_at | timestamptz | |

## 14.2. `portfolio_positions`

| Column | Type | Notes |
|---|---|---|
| id | bigserial PK | |
| portfolio_id | uuid FK | |
| stock_id | int FK | |
| quantity | numeric(20,4) | |
| avg_cost | numeric(18,4) | |
| opened_at | timestamptz | |
| closed_at | timestamptz | nullable |

## 14.3. `portfolio_snapshots` (hypertable)

| Column | Type | Notes |
|---|---|---|
| portfolio_id | uuid FK | |
| snapshot_date | date | |
| total_value | numeric(24,4) | |
| expected_return | numeric(10,6) | |
| volatility | numeric(10,6) | |
| beta | numeric(10,6) | |
| max_drawdown | numeric(10,6) | |
| sector_exposure | jsonb | |
| concentration | numeric(10,6) | |

`PRIMARY KEY (portfolio_id, snapshot_date)`, hypertable.

---

# 15. Governance, Audit, Data Quality

## 15.1. `audit_logs` — append-only (§31, §41)

| Column | Type | Notes |
|---|---|---|
| id | bigserial PK | |
| entity_type | text | e.g. `agent_run`, `model`, `prediction` |
| entity_id | text | |
| action | text | |
| actor | text | user or system |
| payload | jsonb | |
| created_at | timestamptz | |

Application roles have **no UPDATE/DELETE** grants on this table — agents are forbidden from deleting audit logs (§41).

## 15.2. `data_quality_scores` (§39 Data Quality Framework)

| Column | Type | Notes |
|---|---|---|
| id | bigserial PK | |
| dataset | text | e.g. `prices`, `financial_statements` |
| stock_id | int FK | nullable, dataset may be global |
| as_of_date | date | |
| completeness | numeric(5,2) | |
| accuracy | numeric(5,2) | |
| consistency | numeric(5,2) | |
| freshness | numeric(5,2) | |
| uniqueness | numeric(5,2) | |
| validity | numeric(5,2) | |
| overall_score | numeric(5,2) | 0-100 (§39) |
| below_threshold | boolean | blocks downstream usage when true |

---

# 16. Users / Auth (Production phase)

## 16.1. `users`

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| email | text UNIQUE | |
| password_hash | text | |
| role | text | `ADMIN`, `ANALYST`, `VIEWER` |
| created_at | timestamptz | |

## 16.2. `api_keys`

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK | |
| key_hash | text | never store raw key |
| scopes | jsonb | |
| created_at | timestamptz | |
| revoked_at | timestamptz | nullable |

---

# 17. TimescaleDB Hypertable Summary

```text
prices                  -> chunk by trade_date (1 month)
adjusted_prices         -> chunk by trade_date (1 month)
index_prices            -> chunk by trade_date (1 month)
foreign_flows           -> chunk by trade_date (1 month)
prop_trading_flows      -> chunk by trade_date (1 month)
valuation_daily         -> chunk by trade_date (1 month)
macro_indicators        -> chunk by period_date (1 year)
features                -> chunk by trade_date (1 month)
factor_scores           -> chunk by trade_date (1 month)
signals                 -> chunk by trade_date (1 month)
market_regimes          -> chunk by trade_date (1 year)
predictions             -> chunk by trade_date (1 month)
portfolio_snapshots     -> chunk by snapshot_date (1 month)
```

Retention/compression policies are deferred to a later ADR once storage volume is known.

---

# 18. Migration Strategy

- Tool: **Alembic** (SQLAlchemy) under `database/migrations/`.
- One migration per logical change; never edit a migration once merged.
- Seed data (exchanges, sectors, VN30 constituents) lives in `database/seeds/`.
- TimescaleDB hypertable conversion (`create_hypertable(...)`) is executed as a post-create step inside the same migration that creates the base table.

---

# 19. Open Items for Next Iteration

- Confirm restatement policy detail for `financial_statements` bitemporal queries used by the backtester.
- Decide on object storage (S3-compatible) schema for raw document blobs referenced by `documents.storage_path`.
- Decide compression/retention policy per hypertable once data volume for VN30 EOD history is measured.