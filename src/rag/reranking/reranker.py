"""Reranker (RAG_ARCH §5) — deterministic cross-encoder-lite.

Re-scores top-k retrieval hits with a token-overlap + coverage model so
exact-phrase and high-coverage chunks outrank pure vector neighbors.
Pure-Python, no ML deps; swap for a provider rerank API later.
"""

from __future__ import annotations

from src.rag.embedding.hash_embed import tokenize
from src.rag.retrieval.retriever import RankedDoc


def cross_encoder_lite_score(query: str, text: str) -> float:
    """Deterministic re-rank score in [0, 1].

    Average of bigram precision and unigram recall against the query —
    rewards exact phrases and full coverage of query terms.
    """
    qtoks = tokenize(query)
    dtoks = tokenize(text)
    if not qtoks or not dtoks:
        return 0.0
    qset, dset = set(qtoks), set(dtoks)
    recall = len(qset & dset) / len(qset)
    qbigrams = {tuple(qtoks[i : i + 2]) for i in range(len(qtoks) - 1)}
    dbigrams = {tuple(dtoks[i : i + 2]) for i in range(len(dtoks) - 1)}
    bigram = (len(qbigrams & dbigrams) / len(qbigrams)) if qbigrams else 0.0
    return 0.5 * recall + 0.5 * bigram


def rerank(query: str, docs: list[RankedDoc], *, weight: float = 0.35) -> list[RankedDoc]:
    """Blend rerank score into ``final_score`` and re-sort (stable)."""
    if not docs:
        return []
    for d in docs:
        rr = cross_encoder_lite_score(query, f"{d.chunk.title} {d.chunk.text}")
        d.final_score = (1 - weight) * d.final_score + weight * rr
    return sorted(docs, key=lambda r: r.final_score, reverse=True)


__all__ = ["cross_encoder_lite_score", "rerank"]
