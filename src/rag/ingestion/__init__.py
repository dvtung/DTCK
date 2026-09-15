"""Ingestion package — deterministic chunking + store upserts."""

from src.rag.ingestion.chunking import Chunk, chunk_news_item, chunk_text

__all__ = ["Chunk", "chunk_news_item", "chunk_text"]
