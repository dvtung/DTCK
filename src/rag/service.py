"""RAG service — singleton ingestion + retrieval + evidence pipeline (T012).

Owns a ``HashEmbedding`` + ``MemoryVectorStore`` + optional ``QdrantAdapter``
mirror + ``Retriever``.  Call ``ingest_news_items`` once at startup (or via
the worker ``ingest-rag`` command), then ``search`` / ``evidence_for`` serve
the API routers.  Pure-Python baseline; Qdrant mirroring is best-effort.
"""

from __future__ import annotations

from typing import Any

from src.evidence.engine import Evidence, build_evidence, evidence_to_dict
from src.rag.embedding.hash_embed import HashEmbedding
from src.rag.ingestion.chunking import Chunk, chunk_news_item
from src.rag.reranking.reranker import rerank
from src.rag.retrieval.retriever import RankedDoc, Retriever
from src.rag.retrieval.store import MemoryVectorStore, QdrantAdapter


class RagService:
    """Process-wide RAG + evidence service (deterministic baseline)."""

    def __init__(self, dim: int = 128) -> None:
        self._embedder = HashEmbedding(dim=dim)
        self._store = MemoryVectorStore(self._embedder)
        self._qdrant = QdrantAdapter(dim=dim)
        self._retriever = Retriever(self._store, self._embedder)
        self._ingested_docs = 0

    @property
    def size(self) -> int:
        return self._store.size

    @property
    def model_name(self) -> str:
        return self._embedder.model_name

    @property
    def qdrant_available(self) -> bool:
        return self._qdrant.available

    def ingest_news_items(
        self, items: list[dict[str, object]], *, max_chars: int = 800
    ) -> dict[str, int]:
        """Chunk + embed + store news dicts. Returns counts."""
        chunks: list[Chunk] = []
        for it in items:
            chunks.extend(chunk_news_item(it, max_chars=max_chars))
        n = self._store.upsert(chunks)
        vecs = [self._store._vectors[c.chunk_id] for c in chunks]  # noqa: SLF001
        mirrored = self._qdrant.upsert(chunks, vecs)
        self._ingested_docs += len(items)
        return {"docs": len(items), "chunks": n, "mirrored": mirrored}

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        symbol: str = "",
        doc_type: str = "",
        source: str = "",
        rerank_weight: float = 0.35,
    ) -> list[RankedDoc]:
        """Hybrid retrieval + rerank."""
        if not query.strip() or top_k <= 0:
            return []
        docs = self._retriever.retrieve(
            query, top_k=top_k, symbol=symbol, doc_type=doc_type, source=source
        )
        return rerank(query, docs, weight=rerank_weight)

    def evidence_for(
        self,
        query: str,
        *,
        top_k: int = 5,
        symbol: str = "",
        linked_entity_type: str = "",
        linked_entity_id: str = "",
    ) -> list[Evidence]:
        """Retrieve + rerank + build §19 Evidence objects."""
        docs = self.search(query, top_k=top_k, symbol=symbol)
        return build_evidence(
            query, docs,
            linked_entity_type=linked_entity_type,
            linked_entity_id=linked_entity_id,
        )

    def status(self) -> dict[str, Any]:
        """Service health payload for readiness probes."""
        return {
            "chunks": self.size,
            "docs_ingested": self._ingested_docs,
            "model": self.model_name,
            "dim": self._embedder.dim,
            "qdrant_available": self.qdrant_available,
            "qdrant_collection": self._qdrant.collection,
        }

    def to_payload(self, docs: list[RankedDoc]) -> list[dict[str, Any]]:
        return self._retriever.to_payload(docs)

    def evidence_payload(self, evs: list[Evidence]) -> list[dict[str, Any]]:
        return [evidence_to_dict(e) for e in evs]


__all__ = ["RagService"]
