"""Evidence engine per spec §19 — converts retrieval hits to Evidence objects.

Every ``Evidence`` cites chunk-level provenance (doc_id, chunk_id, source,
published_at) and links polymorphically to an analysis/prediction/agent
run/report.  Deterministic confidence = fused retrieval score blended with
source reliability.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.rag.retrieval.retriever import RankedDoc
from src.rag.retrieval.retriever import source_score as _source_score


@dataclass(frozen=True, slots=True)
class Evidence:
    """One verifiable evidence object (§19)."""

    claim: str
    source: str
    source_type: str
    published_at: datetime | None
    data_timestamp: datetime | None
    evidence: str
    confidence: float
    doc_id: str = ""
    chunk_id: str = ""
    symbol: str = ""
    linked_entity_type: str = ""
    linked_entity_id: str = ""


def confidence_for(doc: RankedDoc) -> float:
    """Blend fused retrieval score (70%) with source reliability (30%)."""
    rel = _source_score(doc.chunk.source)
    conf = 0.7 * doc.final_score + 0.3 * rel
    return round(max(0.0, min(1.0, conf)), 4)


def build_evidence(
    query: str,
    docs: list[RankedDoc],
    *,
    linked_entity_type: str = "",
    linked_entity_id: str = "",
    data_timestamp: datetime | None = None,
) -> list[Evidence]:
    """Convert ranked docs into §19 Evidence objects for ``query``."""
    out: list[Evidence] = []
    for d in docs:
        snippet = d.chunk.text[:400]
        out.append(
            Evidence(
                claim=query,
                source=d.chunk.source,
                source_type=d.chunk.doc_type or "news",
                published_at=d.chunk.published_at,
                data_timestamp=data_timestamp,
                evidence=snippet,
                confidence=confidence_for(d),
                doc_id=d.chunk.doc_id,
                chunk_id=d.chunk.chunk_id,
                symbol=d.chunk.symbol,
                linked_entity_type=linked_entity_type,
                linked_entity_id=linked_entity_id,
            )
        )
    return out


def evidence_to_dict(ev: Evidence) -> dict[str, Any]:
    """Serialize an Evidence to its §19 JSON shape."""
    return {
        "claim": ev.claim,
        "source": ev.source,
        "source_type": ev.source_type,
        "published_at": ev.published_at.isoformat() if ev.published_at else None,
        "data_timestamp": ev.data_timestamp.isoformat() if ev.data_timestamp else None,
        "evidence": ev.evidence,
        "confidence": ev.confidence,
        "doc_id": ev.doc_id,
        "chunk_id": ev.chunk_id,
        "symbol": ev.symbol,
        "linked_entity_type": ev.linked_entity_type,
        "linked_entity_id": ev.linked_entity_id,
    }


__all__ = ["Evidence", "build_evidence", "confidence_for", "evidence_to_dict"]
