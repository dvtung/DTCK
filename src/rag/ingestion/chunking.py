"""Deterministic document chunking (§18.1, RAG_ARCHITECTURE §3).

Splits raw documents/news into chunks with structure-aware boundaries
(heading → paragraph → hard window), each carrying provenance metadata
(title, source, published_at, symbol) so Qdrant + PostgreSQL stay linked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Chunk:
    """One retrievable unit with chunk-level provenance."""

    chunk_id: str
    doc_id: str
    text: str
    title: str = ""
    source: str = ""
    doc_type: str = "news"
    symbol: str = ""
    sector: str = ""
    published_at: datetime | None = None
    chunk_index: int = 0
    metadata: dict[str, object] = field(default_factory=dict)


def chunk_text(
    text: str,
    *,
    doc_id: str,
    title: str = "",
    source: str = "",
    doc_type: str = "news",
    symbol: str = "",
    sector: str = "",
    published_at: datetime | None = None,
    max_chars: int = 800,
    overlap_chars: int = 100,
) -> list[Chunk]:
    """Split text into overlapping chunks (deterministic, pure-Python).

    Boundary preference: blank-line paragraph breaks first, then sentence
    ends, then hard character window.  Overlap preserves cross-boundary
    context for embedding.
    """
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    overlap = max(0, min(overlap_chars, max_chars // 2))
    body = (text or "").strip()
    if not body:
        return []
    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    windows: list[str] = []
    buf = ""
    for p in paras:
        candidate = f"{buf}\n\n{p}" if buf else p
        if len(candidate) <= max_chars:
            buf = candidate
        else:
            if buf:
                windows.append(buf)
            while len(p) > max_chars:
                windows.append(p[:max_chars])
                p = p[max_chars - overlap :]
            buf = p
    if buf:
        windows.append(buf)
    chunks: list[Chunk] = []
    for i, w in enumerate(windows):
        chunks.append(
            Chunk(
                chunk_id=f"{doc_id}#c{i}",
                doc_id=doc_id,
                text=w,
                title=title,
                source=source,
                doc_type=doc_type,
                symbol=symbol.upper() if symbol else "",
                sector=sector,
                published_at=published_at,
                chunk_index=i,
            )
        )
    return chunks


def chunk_news_item(item: dict[str, object], *, max_chars: int = 800) -> list[Chunk]:
    """Chunk one news dict (`title`/`content` or `body`) into ``Chunk``s."""
    doc_id = str(item.get("id", item.get("title", "news")))
    body = str(item.get("content", item.get("body", item.get("title", ""))))
    published = item.get("published_at")
    if not isinstance(published, datetime):
        published = None
    return chunk_text(
        body,
        doc_id=doc_id,
        title=str(item.get("title", "")),
        source=str(item.get("source", "")),
        doc_type="news",
        symbol=str(item.get("symbol", "")),
        published_at=published,
        max_chars=max_chars,
    )


__all__ = ["Chunk", "chunk_news_item", "chunk_text"]
