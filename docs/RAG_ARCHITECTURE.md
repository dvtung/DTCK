# RAG ARCHITECTURE

## AI Investment Research & Decision Intelligence Platform

**Version:** 1.0
**Status:** Baseline — derived from SYSTEM_SPECIFICATION.md v1.0 (§18)

---

# 1. Purpose

Build an evidence-backed knowledge base over Vietnamese market documents so agent reasoning cites verifiable sources (§4.4, §19).

---

# 2. Document Corpus (§18.1)

```text
News
Financial Reports
Corporate Disclosures
Annual Reports
Quarterly Reports
Research Reports
Company Information
```

---

# 3. Ingestion Pipeline

```text
Document (PDF/HTML/text)
  ↓ chunking (structure-aware: sections, tables, headings)
  ↓ metadata extraction (symbol, sector, event_type, date, source)
  ↓ embedding (provider abstraction — ADR-005)
  ↓ upsert into Qdrant (payload = metadata; vector = embedding)
  ↓ register metadata row in documents / news tables (DB)
```

- Chunk-level provenance preserved (title, source, published_at, symbol).
- Qdrant + PostgreSQL metadata stay linked via `qdrant_point_id`.

---

# 4. Retrieval Pipeline (§18.2)

```text
User Query
    ↓
Metadata Filter        (symbol, sector, date range, doc_type, source)
    ↓
Vector Search          (dense semantic)
    ↓
Keyword Search         (BM25 on news/documents tables)
    ↓
Recency Weight
    ↓
Source Reliability
    ↓
Reranking
    ↓
Evidence Set           (top-k with scores)
```

Hybrid fusion = dense + sparse (BM25) scores, then reranker (cross-encoder or provider rerank API).

---

# 5. Supplemental Components

- **Embedding service** (`src/rag/embedding`) — provider-abstracted (OpenAI-compatible, local, etc.), versioned embedding models.
- **Retriever** (`src/rag/retrieval`) — hybrid retrieval + metadata filters.
- **Reranker** (`src/rag/reranking`) — optional cross-encoder.
- **Evidence set builder** (`src/evidence`) — converts top-k results into `Evidence` objects (§19).

---

# 6. Evidence Object (§19)

```json
{
  "claim": "...",
  "source": "...",
  "source_type": "financial_report",
  "published_at": "...",
  "data_timestamp": "...",
  "evidence": "...",
  "confidence": 0.91
}
```

Evidence links to: Analysis, Prediction, Agent run, Report (polymorphic via `linked_entity_type/id`).

---

# 7. Evaluation

- Retrieval quality: hit rate @k, MRR, NDCG on a labeled query set.
- Agent hallucination check: every factual claim in agent output must map to an Evidence entry (§38 agent evaluation).
- Freshness bias: recency weighting must prevent stale-but-semantically-similar docs from suppressing recent news.

---

# 7. Qdrant Collection Config

- Distance: Cosine
- Vectors: per embedding model name (multi-vector collections if needed)
- Payload indexes: `symbol`, `published_at`, `source`, `doc_type`

---

# 8. Evaluation