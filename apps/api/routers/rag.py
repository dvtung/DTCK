"""/api/v1/rag + /api/v1/evidence (RAG_ARCHITECTURE §4-6, spec §18/§19)."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from apps.api.services.rag_service import get_rag_service
from src.rag.service import RagService

RagDep = Annotated[RagService, Depends(get_rag_service)]

router = APIRouter(tags=["rag"])


@lru_cache
def _rag() -> RagService:
    return get_rag_service()


@router.get("/api/v1/rag/search", response_model=dict)
def rag_search(
    service: RagDep,
    q: str = Query(default="", min_length=1),
    top_k: int = Query(default=5, ge=1, le=50),
    symbol: str | None = Query(default=None),
    doc_type: str | None = Query(default=None),
    source: str | None = Query(default=None),
) -> dict[str, Any]:
    docs = service.search(
        q, top_k=top_k, symbol=symbol or "",
        doc_type=doc_type or "", source=source or "",
    )
    items = service.to_payload(docs)
    return {"query": q, "items": items, "total": len(items),
            "model": service.model_name}


@router.get("/api/v1/rag/status", response_model=dict)
def rag_status(service: RagDep) -> dict[str, Any]:
    return service.status()


@router.get("/api/v1/evidence", response_model=dict)
def list_evidence(
    service: RagDep,
    q: str = Query(default="", min_length=1),
    top_k: int = Query(default=5, ge=1, le=50),
    symbol: str | None = Query(default=None),
) -> dict[str, Any]:
    evs = service.evidence_for(q, top_k=top_k, symbol=symbol or "")
    return {"query": q, "items": service.evidence_payload(evs),
            "total": len(evs)}
