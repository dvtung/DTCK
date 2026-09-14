# DATA SOURCE DESIGN

## AI Investment Research & Decision Intelligence Platform

**Version:** 1.1
**Status:** Baseline (T002) — candidate providers, selection & credentials plan.
**Scope:** Vietnam stock market (HOSE / HNX / UPCOM), universe starts at VN30.
**Primary Store:** PostgreSQL + TimescaleDB (see `docs/DATABASE_SCHEMA.md`).

> ⚠️ **Verification honesty:** network egress was **not** available when this doc was
> written, so individual provider *endpoint* URLs, exact response shapes, and rate
> limits are marked **`TO VERIFY`** and must be confirmed first in T004. Provider
> *existence*, licensing model, and general capability are well-known public facts.

---

# 1. Objectives & Non-Objectives

## Objectives
- Cover every domain in `docs/DATA_ARCHITECTURE.md` §1 (market, fundamental,
  valuation, macro, corporate events, news) with a **primary and at least one
  fallback** source.
- Prefer **free / official** sources; reserve paid sources for narrow gaps.
- Every source is behind a small **provider abstraction** so swapping a vendor
  never touches pipeline/DB code (mirrors ADR-005 LLM abstraction decision).
- Credentials are **never** in code/Git/images (spec §32, `docs/SECURITY.md`).

## Non-objectives
- No intraday/tick data in Phase 1 (EOD only; intraday later).
- No commercial terminal licensing (Bloomberg/Refinitiv) in MVP.
- We do **not** rely on any single unofficial API as the sole source.

---

# 2. Design Principles (map to spec §4)

| Principle | Consequence for source selection |
|---|---|
| **Data First** (bad data ⇒ bad everything) | Prefer sources with provenance + history; validate & score (§39) |
| **Deterministic calculation** (§4.2) | Valuation/factor numbers are *computed* by the Quant Engine, never taken verbatim from an opaque provider |
| **Survivorship-bias control** (§17) | Keep a **history of universe membership** (VN30/vn100) and `listed_date`/`delisted_date` |
| **Bitemporal fundamentals** (§5.1 DB) | Restated financials must be captured (`valid_from`/`valid_to`), not overwritten |
| **Evidence/provenance** | Every row records `source` + `ingested_at` (batch id) |

---

# 3. Provider Abstraction

Collectors (T004) talk to a thin interface; the concrete *provider* is selected
from `configs/sources.yaml` (machine-readable registry). This doc defines the
contract; T004 implements the classes.

```text
Scheduler (APScheduler, worker)
   │
   ▼
Collector(domain, datatype)          # generic: fetch → validate → normalize → upsert
   │
   ├─▶ DataProvider(abc)             # id, domain, auth, rate_limit, base_headers
   │        └─ provider specific HTTP/GraphQL/RSS client (ssix, vndirect, tcbs, ...)
   ▼
Validator --> Normalizer --> PostgreSQL (idempotent upsert)
```

**Provider contract (fields used by collectors):**

| Field | Meaning |
|---|---|
| `id` | short slug, e.g. `vndirect` |
| `roles` | subset of `market, fundamental, valuation, macro, corporate_events, news` |
| `credential_env` | env var holding the secret (empty string if anonymous) |
| `auth` | `none` \\| `query` \\| `bearer` |
| `free` / `licensed` | cost & licensing flags (informational) |
| `enabled` | `true` to consider at runtime |
| `priority` | higher = preferred; collector falls back on failure/quality gate |

Selection rule: for each `(domain, datatype)` choose the **highest-priority enabled**
provider; if its data fails validation or a `data_quality_scores.overall_score`
gate (§39), fall back to the next.

---

# 4. Recommended Providers by Domain

## 4.1 Market Data (OHLCV, value, mcap, indices, foreign/prop flows)

| Provider | id | Access | Licensed | Coverage | Reliability | Status |
|---|---|---|---|---|---|---|
| **SSI FiniPro** | `ssix_finipro` | free registration, per-user access | yes (SSI official) | symbols, EOD OHLCV, indices, foreign trading, basic fundamentals & news | high | **⇒ chosen primary** |
| VNDirect (finfo) | `vndirect` | anonymous public API | no (unofficial) | EOD OHLCV, indices, foreign flow, financials | medium | fallback |
| TCBS public API | `tcbs` | anonymous public API | no (unofficial) | EOD quotes, some fundamentals | medium | fallback |
| DSC GraphData | `dsc` | anonymous public GraphQL | no (unofficial) | market + financial | medium | fallback |
| HOSE / HNX official | `hose`,`hnx` | listed-data files | required for redistribution | official trading stats, indices | high | enable after licensing |

**Selection:** primary `ssix_finipro`; fallback chain `vndirect → tcbs → dsc`.
Indices (`index_prices`) come from the same vendor (VNINDEX/VN30/…) and are kept
derived-copy only. Foreign/prop trading flows come from the provider's per-symbol
flow endpoints (`TO VERIFY` per-symbol coverage in T004).

## 4.2 Fundamental Data (financial statements, restatements)

| Provider | id | Access | Notes |
|---|---|---|---|
| **SSI FiniPro** | `ssix_finipro` | registration | income/balance/cashflow by fiscal period; **`report_date` present** ⇒ usable for bitemporal windowing |
| VNDirect (finfo) | `vndirect` | anonymous | statement line items; useful cross-check |
| Vietstock | `vietstock` | VIP (paid) | cleanest restatement-adjusted historicals; optional later |

**Restatement handling (bitemporal, DB §5.1):** no Vietnam feed reliably flags
restatements. Plan (decided here) = **snapshot-diff**: on each ingest, compare the
provider's current "as-published" value for `(stock, period)` against the last
stored row; if changed, close the old row (`valid_to = now`) and open a new row
(`valid_from = now`). This yields correct `valid_from`/`valid_to` without
provider cooperation.

## 4.3 Valuation Data

`valuation_daily` (P/E, P/B, EV/EBITDA, EV/Sales, DY, PEG) is **computed by the
Quant Engine** (deterministic, §4.2) from `prices` + `financial_statements`.
Providers are used only to **cross-check** a few snapshot ratios during T005

## 4.4 Macro Data

| Provider | id | Access | Coverage |
|---|---|---|---|
| **GSO (General Statistics Office)** | `gso` | public | GDP, CPI, industrial production |
| **SBV (State Bank of Vietnam)** | `sbv` | public | policy/base rates, credit growth, M2, USDVND reference |
| **IMF / World Bank** | `imf_worldbank` | public APIs | cross-country benchmarks, inflation, FX history |
| TradingEconomics | `tradingeconomics` | paid API | convenient aggregation, optional |

Selection: primary `gso + sbv` (official), complemented by `imf_worldbank`;
`tradingeconomics` optional and **disabled by default** (cost).

## 4.5 Corporate Events

Sources: **SSI FiniPro / HOSE announcements** (earnings, dividends, splits, AGM),
plus **CafeF** (`cafef`) aggregator. `announced_date` and `event_date` both captured
so backtests never look ahead of the announcement (§17).

## 4.6 News (Vietnamese)

| Provider | id | Access | Notes |
|---|---|---|---|
| **CafeF** | `cafef` | public RSS/HTML | financial news; Vietnamese (embed with multilingual model) |
| VnExpress Finance | `vnexpress` | public RSS | broad market news |
| Vietstock | `vietstock` | public RSS | market focus |
| *(optional)* NewsData.io | `newsdata` | paid API | symbol-tagged; requires `NEWS_API_KEY` |

News is stored in `news`/`news_symbols`, embedded to Qdrant in Phase 4 (RAG).
Assign `sector_id`/`event_type`/`sentiment`/`importance` during normalization
(`TO VERIFY` symbol-matching quality in T004).

---

# 5. Domain → Table Mapping (what each source feeds)

| Domain | Tables (`docs/DATABASE_SCHEMA.md`) | Providers |
|---|---|---|
| Market | `prices`, `adjusted_prices`, `index_prices`, `foreign_flows`, `prop_trading_flows` | `ssix_finipro`, `vndirect`, `tcbs`, `dsc` |
| Fundamental | `financial_statements`, `financial_ratios` | `ssix_finipro`, `vndirect`, `vietstock` |
| Valuation | `valuation_daily` | **computed** by Quant Engine (cross-check: `ssix_finipro`) |
| Macro | `macro_indicators` | `sbv`, `gso`, `imf_worldbank`, `tradingeconomics` |
| Corporate events | `corporate_events` | `ssix_finipro`, `hose`, `cafef` |
| News | `news`, `news_symbols` | `cafef`, `vnexpress`, `vietstock`, `newsdata` |

---

# 6. Credentials & Secrets Plan

Guided by `docs/SECURITY.md` §2 (no secrets in code/Git/images; env-only).

| Purpose | Env var (names only — empty in `.env.example`) | Provider(s) |
|---|---|---|
| Primary market/fundamental provider | `FINIPRO_ACCESS_TOKEN` | `ssix_finipro` |
| Paid news/keyword API (optional) | `NEWS_API_KEY` | `newsdata` |
| Macro aggregation (optional, paid) | `TRADINGECONOMICS_API_KEY` | `tradingeconomics` |
| Market data selector (repeat of registry) | `MARKET_DATA_PROVIDER`, `MARKET_DATA_API_KEY` | generic |
| Fundamental selector | `FUNDAMENTAL_DATA_PROVIDER` | generic |
| News selector | `NEWS_PROVIDER`, `NEWS_API_KEY` | generic |

Rules:
- All provider secrets are **optional**; anonymous providers run without keys.
- `.env.example` documents **names only with empty values** (already true for the
  generic ones; `FINIPRO_ACCESS_TOKEN` etc. are added).
- The worker's data-fetch loop lives in the private Docker network; only the
  specific provider host is reachable (egress whitelist, §32 / `docs/SECURITY.md` §7).
- Production: keys injected at deploy time from a secret manager; never baked.

# 7. Fallback / Failover Matrix

| If (primary) fails | Then (fallback chain) | Gate |
|---|---|---|
| `ssix_finipro` market | `vndirect` → `tcbs` → `dsc` | validation or quality-score gate |
| `ssix_finipro` fundamentals | `vndirect` → `vietstock` | report_date sanity |
| `sbv`/`gso` | `imf_worldbank` (+ `tradingeconomics` if licensed) | freshness window |
| `cafef` | `vnexpress` → `vietstock` | dedup on `(source,title)` |

Fallback is **not** silent: each switch is recorded in `audit_logs` so provenance
is always reproducible.

---

# 8. Open Items / TO VERIFY (blocking T004 collector work)

1. **FiniPro** registration flow, token mechanics, and per-call rate limits.
2. Exact endpoint URLs & response schemas for `vndirect`, `tcbs`, `dsc`
   (undocumented APIs — must be snapshot-tested).
3. Per-symbol coverage of **foreign flow / prop trading** in fallback vendors.
4. Vietnam suppliers' ability to express **`report_date` (filing date)** and how
   **restatement diffs** look — validates the snapshot-diff design in §4.2.
5. News **symbol-matching** accuracy (Vietnamese entity matching) for `news_symbols`.
6. Licensing read on HOSE/HNX official feeds (corporate-action factors for
   `adjusted_prices`) before enabling `hose`/`hnx` providers.
quality scoring; they are not the source of truth.