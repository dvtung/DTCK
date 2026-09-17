"""Deterministic RAG service dependency (T012) — process-wide singleton."""

from __future__ import annotations

from functools import lru_cache

from src.rag.service import RagService


@lru_cache
def get_rag_service() -> RagService:
    """Provide the process-wide RAG + evidence service (MVP-2).

    Lazily seeded from the shared ``MarketService`` news fixture on first use so
    the endpoints work with zero setup (empty index is a valid baseline).
    """
    svc = RagService()
    try:
        from apps.api.dependencies import get_market_service

        items = get_market_service().list_news()
        if items:
            svc.ingest_news_items(items)
    except Exception:  # noqa: BLE001 — empty index is a valid baseline
        pass
    return svc


__all__ = ["get_rag_service"]
