"""Embedding package — provider-abstracted document/query vectors."""

from src.rag.embedding.hash_embed import (
    EmbeddingModel,
    HashEmbedding,
    cosine_similarity,
    tokenize,
)

__all__ = ["EmbeddingModel", "HashEmbedding", "cosine_similarity", "tokenize"]
