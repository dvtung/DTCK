"""Hybrid retrieval pipeline per spec §18.2 + RAG_ARCHITECTURE §4.

Query → metadata filter → vector search → keyword search → recency weight
→ source reliability → rerank → evidence set.

All stages are pure-Python and deterministic; each contributes a named
score so the final ranking is explainable (stored on ``RankedDoc``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.rag.embedding.hash_embed import EmbeddingModel, tokenize
from src.rag.ingestion.chunking import Chunk
from src.rag.retrieval.store import MemoryVectorStore, ScoredChunk

# Source reliability weights (RAG_ARCH §4) — reputable wires rank higher.
SOURCE_RELIABILITY: dict[str, float] = {
    "cafef": 0.9,
    "vietstock": 0.85,
    "vnexpress": 0.8,
    "ssi": 0.95,
    "vcsc": 0.9,
}
DEFAULT_RELIABILITY = 0.6

# Fusion weights: dense + sparse + recency + reliability → final score.
W_VECTOR = 0.5
W_KEYWORD = 0.25
W_RECENCY = 0.15
W_SOURCE = 0.10
RECENCY_HALF_LIFE_DAYS = 30.0


@dataclass
class RankedDoc:
    """A chunk with the full explainable score breakdown."""

    chunk: Chunk
    final_score: float
    vector_score: float = 0.0
    keyword_score: float = 0.0
    recency_score: float = 0.0
    source_score: float = 0.0
    vector: list[float] = field(default_factory=list)


def keyword_score(query: str, text: str) -> float:
    """BM25-lite: IDF-weighted token overlap in [0, 1]."""
    qtoks = set(tokenize(query))
    if not qtoks:
        return 0.0
    dtoks = set(tokenize(text))
    hits = qtoks & dtoks
    if not hits:
        return 0.0
    # Longer query terms carry more signal (rough IDF proxy).
    w_hit = sum(min(len(t), 8) for t in hits)
    w_all = sum(min(len(t), 8) for t in qtoks)
    return w_hit / w_all if w_all else 0.0


def recency_score(published_at: datetime | None, now: datetime | None = None) -> float:
    """Exponential decay with 30-day half-life; undated docs score 0.5."""
    if published_at is None:
        return 0.5
    ref = now or datetime.now(tz=UTC)
    pub = published_at if published_at.tzinfo else published_at.replace(tzinfo=UTC)
    age_days = max(0.0, (ref - pub).total_seconds() / 86400.0)
    return math.exp(-age_days * math.log(2) / RECENCY_HALF_LIFE_DAYS)


def source_score(source: str) -> float:
    """Source reliability weight in [0, 1]."""
    return SOURCE_RELIABILITY.get((source or "").lower(), DEFAULT_RELIABILITY)


def fuse_scores(
    vector: float, keyword: float, recency: float, source: float
) -> float:
    """Weighted fusion of the four stage scores."""
    return (
        W_VECTOR * vector
        + W_KEYWORD * keyword
        + W_RECENCY * recency
        + W_SOURCE * source
    )


class Retriever:
    """Hybrid retriever over a ``MemoryVectorStore`` (§18.2)."""

    def __init__(self, store: MemoryVectorStore, embedder: EmbeddingModel) -> None:
        self._store = store
        self._embedder = embedder

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        symbol: str = "",
        doc_type: str = "",
        source: str = "",
        now: datetime | None = None,
    ) -> list[RankedDoc]:
        """Run the full pipeline and return top-k ranked docs."""
        qvec = self._embedder.embed(query)
        # Over-fetch from vector stage; keyword/recency/source re-rank.
        candidates: list[ScoredChunk] = self._store.search(
            qvec, top_k=max(top_k * 4, 20),
            symbol=symbol, doc_type=doc_type, source=source,
        )
        ranked: list[RankedDoc] = []
        for cand in candidates:
            kw = keyword_score(query, f"{cand.chunk.title} {cand.chunk.text}")
            rec = recency_score(cand.chunk.published_at, now)
            src = source_score(cand.chunk.source)
            final = fuse_scores(cand.vector_score, kw, rec, src)
            ranked.append(
                RankedDoc(
                    chunk=cand.chunk, final_score=final,
                    vector_score=cand.vector_score, keyword_score=kw,
                    recency_score=rec, source_score=src,
                    vector=cand.vector,
                )
            )
        ranked.sort(key=lambda r: r.final_score, reverse=True)
        return ranked[: max(0, top_k)]

    def to_payload(self, docs: list[RankedDoc]) -> list[dict[str, Any]]:
        """Serialize ranked docs for API responses."""
        return [
            {
                "chunk_id": d.chunk.chunk_id,
                "doc_id": d.chunk.doc_id,
                "title": d.chunk.title,
                "source": d.chunk.source,
                "doc_type": d.chunk.doc_type,
                "symbol": d.chunk.symbol,
                "published_at": d.chunk.published_at.isoformat()
                if d.chunk.published_at else None,
                "text": d.chunk.text[:500],
                "scores": {
                    "final": round(d.final_score, 4),
                    "vector": round(d.vector_score, 4),
                    "keyword": round(d.keyword_score, 4),
                    "recency": round(d.recency_score, 4),
                    "source": round(d.source_score, 4),
                },
            }
            for d in ranked_docs(docs)
        ]


def ranked_docs(docs: list[RankedDoc]) -> list[RankedDoc]:
    return sorted(docs, key=lambda r: r.final_score, reverse=True)


__all__ = [
    "RankedDoc",
    "Retriever",
    "SOURCE_RELIABILITY",
    "fuse_scores",
    "keyword_score",
    "ranked_docs",
    "recency_score",
    "source_score",
]
