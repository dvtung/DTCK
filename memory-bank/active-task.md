# Memory Bank — Active Task

**ID:** `T012 — News ingestion + RAG (Qdrant) + evidence engine (MVP-2)`
**State:** COMPLETED (2026-09-15)

**Goal:** Evidence-backed knowledge base over VN market documents per spec §18/§19 + `docs/RAG_ARCHITECTURE.md`: deterministic chunking, provider-abstracted embeddings, in-memory cosine store with optional Qdrant adapter, hybrid retrieval (vector + keyword + recency + source reliability), rerank, §19 Evidence objects, 3 REST endpoints.

**Scope:** `src/rag/embedding/`, `src/rag/ingestion/`, `src/rag/retrieval/`, `src/rag/reranking/`, `src/evidence/`, `apps/api/routers/rag.py`, `apps/api/services/rag_service.py`, `apps/api/main.py` (rag router + readyz qdrant status), `tests/unit/test_rag_evidence.py`, docs + memory-bank.

**Constraints:** No new hard deps (qdrant-client NOT installed; optional import only). Deterministic offline-first. Ruff + mypy strict clean. Unit tests, no live Qdrant/LLM needed.

**Acceptance:**
- [x] `ruff check .` clean
- [x] `mypy src/ apps/` clean (102 source files)
- [x] `pytest -q` all pass — 232 total (was 209; +20 RAG/evidence +3 API)
- [x] `docs/htmldocs/` updated (status/modules/index/api/structure)
- [x] memory-bank updated (tasks/current-state/known-issues/changelog)
