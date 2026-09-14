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
| 2026-09-13 | Hypertables | `predictions` stays a **regular table** (not hypertable) although §17 lists it. TimescaleDB requires the partition column in every unique index, and `prediction_evaluations.prediction_id` FK-refs `predictions.id` | Preserves FK integrity; prediction volume is low |
| 2026-09-13 | Hypertables | `signals` PK is composite `(id, trade_date)` (surrogate `id` is not standalone-unique) | TimescaleDB requires the partition column in the unique index |
| 2026-09-13 | Seeds | VN30 universe seeded as a **baseline** list (30 constituents) | Bootstraps MVP; real membership must be refreshed by the Phase-1 feed |
| 2026-09-13 | Schema source | SQLAlchemy models in `src/common/models/` are the single source of truth; migration 0001 uses `Base.metadata.create_all` for tables + `create_hypertable` for time-series | DRY; models and DB never drift |
| 2026-09-13 | Valuation data | `valuation_daily` is **computed by the Quant Engine**, not ingested (§4.2 deterministic-first) | P/E, P/B, EV/EBITDA… must be reproducible & auditable; vendors only cross-check |
| 2026-09-13 | Data sources | SSI FiniPro = primary provider (market/fundamental/events/news); VNDirect→TCBS→DSC as market fallbacks; SBV+GSO+IMF/WB for macro; CafeF/VnExpress/Vietstock for news | Free/official first, paid optional; no single unofficial API as sole source (spec §4.1) |
| 2026-09-13 | Restatements | Bitemporal `financial_statements` maintained by **snapshot-diff** (close `valid_to`, open new `valid_from` on change) | No Vietnam feed reliably flags restatements; makes as-of queries look-ahead-safe (§17) |
| 2026-09-13 | Fallbacks | Provider failover recorded in `audit_logs` (not silent) | Provenance must stay reproducible (§31) |
| 2026-09-14 | Provider abstraction | `DataProvider` ABC defines `fetch_eod/fetch_index/fetch_news` with `NotImplementedError` defaults; `FixtureProvider` (offline, deterministic) + `HttpJsonProvider` (configurable JSON-over-HTTP) implement the contract | Lets collectors/quality run fully offline for testing; swapping vendors is a config change, not a code change |
| 2026-09-14 | Quality scoring | 6 dimensions (§39) with fixed weights; missing dimensions excluded and overall renormalized (not faked); `freshness_score` uses `Decimal` arithmetic to avoid float drift | Deterministic, auditable quality gate; prevents silent precision loss |
| 2026-09-14 | Symbol resolution | `normalize_*` use `None` instead of `object()` sentinel for unknown symbols | mypy can narrow `Decimal | None` after `is None` check; `object` sentinel broke type narrowing |
| 2026-09-14 | Technical indicators | Pure-Python (no numpy) for MVP; each function accepts `list[float]` and returns `list[float | None]` (None = warmup); RSI uses Wilder's smoothing; EMA seeded with SMA; Bollinger uses population std | Deterministic, testable, dependency-free; VN30 = 30 stocks so perf is adequate |
| 2026-09-14 | Test file mypy | `[tool.mypy.overrides]` for `tests.*` disables `no-untyped-def`, `arg-type`, `no-untyped-call`, `operator`, `truthy-bool`, `type-var` | Test helpers with `**over` dict unpacking and list-index None checks are correct but can't be statically verified; tests are the spec |
| 2026-09-14 | Quant factors | Pure-Python deterministic; `None` on zero denominators/div-by-zero; volatility = annualized log-return std (sqrt(252)); beta = rolling cov/var; percentile rank = strictly-less-than (0-100); scoring uses §12 baseline weights with renormalization | Same testability/auditability rationale as T006; `None`-propagation prevents silent garbage; baseline weights are assumptions to validate via backtests (§12 warning) |
| 2026-09-14 | Static docs site | `docs/htmldocs/` (Vietnamese) is a **living doc**: every task that changes source/schema/configs/behavior MUST update the affected htmldoc pages in the same task and re-validate HTML | Prevents docs drift; keeps the static site trustworthy as the project evolves |