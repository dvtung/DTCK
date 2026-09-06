# Memory Bank — Architecture Decision Records

**Last updated:** 2026-09-06
**ADRs recorded from spec §53 (ADR-001 … ADR-007). Status: ACCEPTED by spec.**

| ADR | Decision | Reason |
|---|---|---|
| **ADR-001** | Quantitative calculations separated from LLM | Deterministic, testable, reproducible |
| **ADR-002** | Qdrant is the initial vector database | Suitable for doc/news RAG; fits existing vector-search architecture |
| **ADR-003** | PostgreSQL/TimescaleDB is the primary structured store | Minimize infrastructure complexity during MVP |
| **ADR-004** | Kafka/Airflow deferred | Infrastructure scales with actual workload |
| **ADR-005** | LLM provider abstracted | Avoid vendor lock-in |
| **ADR-006** | AI output uses structured schema (Pydantic) | Validation, storage, API integration, reproducibility |
| **ADR-007** | Backtesting is a first-class component | Investment signals must be empirically validated |

---

## Suggestions deferred for future ADRs

- TimescaleDB compression/retention policy per hypertable (wait for real volume).
- Object storage (S3-compatible) layout for raw documents/backtest artifacts.
- API auth scheme details (JWT vs API-key-only) — decided at Production phase.
- Task queue choice (Redis/Celery vs plain worker set) — Production phase.