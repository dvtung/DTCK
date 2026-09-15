"""Deterministic, hash-based text embedding (offline fallback, ADR-005).

Produces L2-normalized float vectors from token hashes so the RAG pipeline
runs with zero network and zero ML deps.  Swap for a provider-backed embedder
(OpenAI-compatible / local) without touching callers — same ``EmbeddingModel``
protocol.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

_TOKEN_RE = re.compile(r"[a-z0-9\u00c0-\u1ef9]+")


class EmbeddingModel(Protocol):
    """Provider abstraction for document/query embeddings (ADR-005)."""

    @property
    def dim(self) -> int: ...

    @property
    def model_name(self) -> str: ...

    def embed(self, text: str) -> list[float]: ...

    def embed_many(self, texts: list[str]) -> list[list[float]]: ...


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens (Unicode-aware for Vietnamese)."""
    return _TOKEN_RE.findall(text.lower())


class HashEmbedding:
    """Deterministic hash embedding — offline baseline, no ML deps.

    Each token hashes to one of ``dim`` buckets; bucket counts are
    L2-normalized.  Queries and documents share the same space, so cosine
    similarity ranks genuinely overlapping text higher than noise.
    """

    def __init__(self, dim: int = 128, model_name: str = "hash-128-v1") -> None:
        if dim <= 0:
            raise ValueError("dim must be positive")
        self._dim = dim
        self._name = model_name

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return self._name

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        for tok in tokenize(text or ""):
            h = int(hashlib.sha256(tok.encode("utf-8")).hexdigest(), 16)
            vec[h % self._dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two equal-length vectors (0 when degenerate)."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


__all__ = [
    "EmbeddingModel",
    "HashEmbedding",
    "cosine_similarity",
    "tokenize",
]
