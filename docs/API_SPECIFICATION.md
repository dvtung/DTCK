# API SPECIFICATION

## AI Investment Research & Decision Intelligence Platform

**Version:** 1.0 (draft)
**Status:** Baseline — derived from SYSTEM_SPECIFICATION.md v1.0 (§28)

---

# 1. Conventions

- Base path: `/api/v1`
- Format: JSON, `application/json`
- Errors: `{ "error": { "code": str, "message": str, "details": optional } }` with standard HTTP status codes
- Pagination: query params `limit` (default 20, max 200), `offset` (default 0); responses include `{ "items": [...], "total": n, "limit": l, "offset": o }`
- **Performance (§45):** non-LLM endpoints target P95 < 500 ms — LLM latency is excluded from core API latency budget.

---

# 2. API Groups (§28)

## 2.1. `/api/v1/market`

| Method | Path | Description |
|---|---|---|
| GET | `/market/indices` | index snapshots (VNINDEX, VN30, …) |
| GET | `/market/regime` | current market regime + confidence (§13) |
| GET | `/market/regime/history` | regime history |
| GET | `/market/breadth` | advancers/decliners, participation |

## 2.2. `/api/v1/stocks`

| Method | Path | Description |
|---|---|---|
| GET | `/stocks` | stock list w/ filters (exchange, sector, universe VN30/VN100) |
| GET | `/stocks/{symbol}` | profile + latest snapshot |
| GET | `/stocks/{symbol}/prices` | OHLCV series (start/end, adjusted flag) |
| GET | `/stocks/{symbol}/ranking` | rank + score decomposition (§43) |
| GET | `/stocks/ranked` | universe ranking with scores |

## 2.3. `/api/v1/fundamentals`

| Method | Path | Description |
|---|---|---|
| GET | `/fundamentals/{symbol}/statements` | income/balance/cashflow w/ period filter |
| GET | `/fundamentals/{symbol}/ratios` | ratio history |
| GET | `/fundamentals/{symbol}/quality` | data quality score + status (§39) |

## 2.4. `/api/v1/technical`

| Method | Path | Description |
|---|---|---|
| GET | `/technical/{symbol}/indicators` | RSI, MACD, MA, Bollinger, ATR, ADX… |
| GET | `/technical/{symbol}/features` | feature-store rows (feature_version filter) |

## 2.5. `/api/v1/valuation`

| Method | Path | Description |
|---|---|---|
| GET | `/valuation/{symbol}/summary` | P/E, P/B, EV/EBITDA, DY, PEG + industry percentile |
| GET | `/valuation/{symbol}/history` | historical valuation bands |

## 2.6. `/api/v1/news`

| Method | Path | Description |
|---|---|---|
| GET | `/news` | filters: symbol, sector, date range, source, sentiment |
| POST | `/news/search` | hybrid RAG search → evidence set (§18.2, §19) |

## 2.7. `/api/v1/analysis`

| Method | Path | Description |
|---|---|---|
| POST | `/analysis/request` | enqueue agent analysis run (async) |
| GET | `/analysis/request/{agent_run_id}` | status + result (structured `InvestmentAnalysis`) |
| GET | `/analysis/{symbol}/latest` | latest stored analysis |

Async pattern: POST returns `202 + { agent_run_id }`; poll GET until `SUCCESS/FAILED/TIMEOUT` (§45).

## 2.8. `/api/v1/predictions`

| Method | Path | Description |
|---|---|---|
| GET | `/predictions/{symbol}` | stored predictions (model/horizon filter) |
| GET | `/predictions/evaluations` | realised outcome tracking (§26) |

## 2.9. `/api/v1/portfolio`

| Method | Path | Description |
|---|---|---|
| GET | `/portfolio/summary` | value, exposure, concentration, drawdown (§27) |
| GET | `/portfolio/positions` | positions + linting signals |

## 2.10. `/api/v1/backtests`

| Method | Path | Description |
|---|---|---|
| POST | `/backtests` | create/run a backtest (sync or async param) |
| GET | `/backtests` | list runs |
| GET | `/backtests/{id}` | overview + params |
| GET | `/backtests/{id}/metrics` | metrics table (§15) |
| GET | `/backtests/{id}/trades` | trade log |

## 2.11. `/api/v1/agents`

| Method | Path | Description |
|---|---|---|
| GET | `/agents` | registry listing (version, status, tools) |
| GET | `/agents/runs` | run history (§31) |
| GET | `/agents/runs/{agent_run_id}` | full audit record: prompts, tool calls, tokens, latency |

---

# 3. Authentication & Authorization (Production)

- `POST /api/v1/auth/login` → JWT (access + refresh). Invalid credentials → **401** with the
  `invalid_credentials` error envelope (the DB-free MVP compares against a deterministic demo
  identity via `secrets.compare_digest`; production replaces it with JWT issuance, §32).
- API keys: `Authorization: Bearer <api_key>`; DB stores only `key_hash` (§32, see SECURITY.md).
- RBAC roles: `ADMIN`, `ANALYST`, `VIEWER`.
- Rate limiting per user/key on LLM-backed endpoints (cost control §47).

---

# 4. Common Behaviors

- **Data freshness:** responses include `data_timestamp` / `as_of`; guardrails flag stale data (§42).
- **Evidence:** LLM-derived endpoints return `evidence: [Evidence]` and `confidence`; never raw numbers without a deterministic source.
- **Determinism:** quant/valuation/technical endpoints are pure reads of precomputed stores; no computation at request time for hot paths.