# Memory Bank — Decisions

**Last updated:** 2026-09-06

A living log of project decisions (why we chose what). Formal ADRs live in `architecture-decisions.md`; this file tracks decisions at any level.

| Date | Context | Decision | Rationale |
|---|---|---|---|
| 2026-09-06 | Phase-0 kickoff | Adopt spec §35 repo layout verbatim (`apps/`, `src/<domain>/…`, `database/`, `docs/`, `memory-bank/`, `offline_package/`) | Spec mandates structure; keeps future phases predictable |
| 2026-09-06 | Primary store | PostgreSQL + TimescaleDB hypertables for all time-series (§7/§9) | ADR-003; minimizes infra complexity for MVP |
| 2026-09-06 | Vector store | Qdrant (ADR-002) | Compatibility with existing vector-search experience of the team |
| 2026-09-06 | Quant vs LLM | Deterministic engine only for financial/technical numbers (ADR-001) | Reproducibility, testability, cost (§47) |
| 2026-09-06 | Backtesting | First-class component (ADR-007) | Strategies must be empirically validated before producing signals |
| 2026-09-06 | LLM provider | Abstraction layer (ADR-005) | Avoid vendor lock-in |
| 2026-09-06 | Agent order | No agent work until Data+Quant+Backtest baseline is verifiable (§57) | Spec's explicit guard; prevents building on sand |
| 2026-09-06 | Migrations | Alembic; hypertable creation inside same migration | Standardized, versioned schema evolution |