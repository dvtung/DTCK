# Memory Bank — Known Issues

**Last updated:** 2026-09-15

| ID | Area | Issue | Status | Notes |
|---|---|---|---|---|
| KI-001 | Data | No data source selected for VN EOD OHLCV, financials, news | **RESOLVED (design)** | T002 selected providers (`docs/DATA_SOURCES.md`, `configs/sources.yaml`); FiniPro = primary, VNDirect/TCBS/DSC fallbacks, SBV/GSO/IMF-WB macro, CafeF/VnExpress/Vietstock news |
| KI-006 | Data | Provider endpoint URLs / response schemas / rate limits unverified (network egress unavailable during T002) | OPEN | Must be confirmed in T004 before first collector run; see `docs/DATA_SOURCES.md` §8 |
| KI-007 | Data | No provider credentials obtained yet (`FINIPRO_ACCESS_TOKEN` etc. empty) | OPEN | Blocks live collection in T004; anonymous fallbacks still testable |
| KI-002 | Infra | Local Python is 3.14.4 — dependency pins (SQLAlchemy/Timescale, LangGraph, etc.) must be verified against it; Docker images use pinned versions instead | PARTIALLY VERIFIED | DB deps (SQLAlchemy 2.0.52, Alembic 1.20, psycopg 3.3) validated locally on 3.14; heavy ML/LLM stack still unverified |
| KI-003 | Docs | `docs/DATABASE_SCHEMA.md` §19 open items: bitemporal restatement policy detail, object-storage path format, per-hypertable retention/compression | OPEN | Design implemented; the §19 items do not block schema/migrations |
| KI-004 | Infra | Docker services actually started/verified end-to-end | RESOLVED | `docker compose` stack up & healthy; DB migration + seeds verified against running TimescaleDB (2026-09-13) |
| KI-005 | Repo | Root spec files were copied (`docs/`) — originals still at repo root; keep in sync until removal decision | OPEN | Decide whether to keep single canonical copy at root or in docs/ |
| KI-008 | API | `apps/api` serves an **in-memory synthetic** `MarketService` (7 base symbols, 60 business days); no TimescaleDB wiring yet | OPEN (by design) | Router contracts are final; swap service for a SQLAlchemy repository without touching routers. Blocks nothing until the persistence layer goes live |
| KI-009 | Backtest | T009 engine validated on **synthetic/fixture price series only** — no real VN market history loaded | OPEN | Depends on KI-006/KI-007 (live collection). Metrics math is unit-tested against hand-computed values; strategy results are not yet meaningful |
| KI-010 | Dashboard | T011 dashboard renders **synthetic in-memory data** (in-process `MarketService` fallback) until TimescaleDB + real data are wired | OPEN (by design) | Same KI-008 root cause; HTTP client will hit the live API with zero dashboard changes once routers serve DB-backed payloads |
| KI-011 | RAG | T012 RAG index is built from **synthetic in-memory news** (same `MarketService` fixture); `qdrant_client` not installed → in-memory vector store is the baseline, Qdrant mirror is best-effort | OPEN (by design) | Contract + retrieval math are unit-tested (232 tests); swap `MemoryVectorStore` → Qdrant by installing the client and pointing `QDRANT_HOST`. Real news collection blocked by KI-006/KI-007 |

---

## Working rules

- Anything marked OPEN blocks downstream work only when it is listed as a dependency.
- Never close an issue without recording who verified the fix and when.