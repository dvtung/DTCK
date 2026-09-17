"""In-memory cosine vector store + optional Qdrant adapter (RAG_ARCH §7).

Default path is pure-Python and deterministic (no network, no ML deps).
When ``qdrant-client`` is installed AND ``QDRANT_URL`` is reachable, the
``QdrantAdapter`` mirrors upserts/searches to a real collection; the
in-memory index always remains the source of truth for tests.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from typing import Any

from src.rag.embedding.hash_embed import EmbeddingModel, cosine_similarity
from src.rag.ingestion.chunking import Chunk

PAYLOAD_INDEXES = ("symbol", "published_at", "source", "doc_type")


def stable_point_id(chunk_id: str) -> int:
    """Process-stable positive 63-bit id for a chunk (never ``hash()`` — that
    is randomized per process and would break Qdrant upsert idempotency)."""
    digest = hashlib.sha256(chunk_id.encode("utf-8")).digest()[:8]
    return int.from_bytes(digest, "big") >> 1


@dataclass
class ScoredChunk:
    """A chunk with its vector similarity score."""

    chunk: Chunk
    vector_score: float
    vector: list[float] = field(default_factory=list)


class MemoryVectorStore:
    """Deterministic in-memory cosine store (baseline, no deps)."""

    def __init__(self, embedder: EmbeddingModel) -> None:
        self._embedder = embedder
        self._chunks: dict[str, Chunk] = {}
        self._vectors: dict[str, list[float]] = {}

    @property
    def size(self) -> int:
        return len(self._chunks)

    @property
    def model_name(self) -> str:
        return self._embedder.model_name

    @property
    def dim(self) -> int:
        return self._embedder.dim

    def upsert(self, chunks: list[Chunk]) -> int:
        """Embed + store chunks. Returns number upserted."""
        if not chunks:
            return 0
        vecs = self._embedder.embed_many([c.text for c in chunks])
        for c, v in zip(chunks, vecs, strict=True):
            self._chunks[c.chunk_id] = c
            self._vectors[c.chunk_id] = v
        return len(chunks)

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int = 10,
        symbol: str = "",
        doc_type: str = "",
        source: str = "",
    ) -> list[ScoredChunk]:
        """Cosine search with payload pre-filters (symbol/doc_type/source)."""
        scored: list[ScoredChunk] = []
        sym = symbol.upper() if symbol else ""
        for cid, chunk in self._chunks.items():
            if sym and chunk.symbol != sym:
                continue
            if doc_type and chunk.doc_type != doc_type:
                continue
            if source and chunk.source != source:
                continue
            score = cosine_similarity(query_vector, self._vectors[cid])
            scored.append(ScoredChunk(chunk=chunk, vector_score=score,
                                      vector=self._vectors[cid]))
        scored.sort(key=lambda s: s.vector_score, reverse=True)
        return scored[: max(0, top_k)]

    def clear(self) -> None:
        self._chunks.clear()
        self._vectors.clear()

    def vectors_for(self, chunks: list[Chunk]) -> list[list[float]]:
        """Stored embeddings for ``chunks`` (public API for mirror adapters)."""
        return [self._vectors[c.chunk_id] for c in chunks]


class QdrantAdapter:
    """Optional mirror to a real Qdrant collection (best-effort, offline-safe).

    All methods no-op gracefully when ``qdrant-client`` is missing or the
    server is unreachable — the in-memory store keeps working.
    """

    def __init__(
        self,
        collection: str = "dtck_docs",
        url: str | None = None,
        dim: int = 128,
    ) -> None:
        self.collection = collection
        self.url = url or os.getenv("QDRANT_URL", "http://localhost:6333")
        self.dim = dim
        self.available = False
        try:
            from qdrant_client import QdrantClient  # type: ignore[import-not-found]
            from qdrant_client.models import (  # type: ignore[import-not-found]
                Distance,
                VectorParams,
            )
            client: Any = QdrantClient(url=self.url, timeout=2.0)
            cols = client.get_collections().collections
            if self.collection not in {c.name for c in cols}:
                client.create_collection(
                    collection_name=self.collection,
                    vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
                )
            self._client = client
            self.available = True
        except Exception:  # noqa: BLE001 — offline fallback is the design
            self._client = None

    def ping(self) -> bool:
        """Best-effort connectivity check (False when offline/uninstalled)."""
        if not self.available or self._client is None:
            return False
        try:
            self._client.get_collections()
            return True
        except Exception:  # noqa: BLE001
            self.available = False
            return False

    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> int:
        """Mirror chunks to Qdrant. Returns mirrored count (0 when offline)."""
        if not self.available or not chunks:
            return 0
        try:
            from qdrant_client.models import PointStruct
            points = [
                PointStruct(
                    id=stable_point_id(c.chunk_id),
                    vector=v,
                    payload={
                        "chunk_id": c.chunk_id, "doc_id": c.doc_id,
                        "title": c.title, "source": c.source,
                        "doc_type": c.doc_type, "symbol": c.symbol,
                        "published_at": c.published_at.isoformat()
                        if c.published_at else None,
                    },
                )
                for c, v in zip(chunks, vectors, strict=True)
            ]
            self._client.upsert(collection_name=self.collection, points=points)
            return len(points)
        except Exception:  # noqa: BLE001
            self.available = False
            return 0


__all__ = [
    "MemoryVectorStore",
    "QdrantAdapter",
    "ScoredChunk",
    "PAYLOAD_INDEXES",
    "stable_point_id",
]
