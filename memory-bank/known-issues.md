# Memory Bank — Known Issues

**Last updated:** 2026-09-06

| ID | Area | Issue | Status | Notes |
|---|---|---|---|---|
| KI-001 | Data | No data source selected/ credentialed yet for VN EOD OHLCV, financials, news | OPEN | Blocks Phase 1 collectors; candidate sources to evaluate in T002 |
| KI-002 | Infra | Local Python is 3.14.4 — dependency pins (SQLAlchemy/Timescale, LangGraph, etc.) must be verified against it; Docker images use pinned versions instead | OPEN | Validate before `pip install` of heavy ML stack |
| KI-003 | Docs | `docs/DATABASE_SCHEMA.md` has open design questions (bitemporal restatement policy detail, object-storage path format, per-hypertable retention) | OPEN | See DATABASE_SCHEMA.md §19 |
| KI-004 | Infra | Docker services not yet actually started/verified end-to-end (config only passed `docker compose config`) | OPEN | T002+ startup smoke test |
| KI-005 | Repo | Root spec files were copied (`docs/`) — originals still at repo root; keep in sync until removal decision | OPEN | Decide whether to keep single canonical copy at root or in docs/ |

---

## Working rules

- Anything marked OPEN blocks downstream work only when it is listed as a dependency.
- Never close an issue without recording who verified the fix and when.