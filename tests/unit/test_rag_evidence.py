"""Deterministic RAG + evidence unit tests (T012, spec §18/§19).

No network, no ML deps, no live Qdrant — the hash embedder and in-memory
store make every assertion exact.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.evidence.engine import build_evidence, confidence_for, evidence_to_dict
from src.rag.embedding.hash_embed import HashEmbedding, cosine_similarity, tokenize
from src.rag.ingestion.chunking import chunk_news_item, chunk_text
from src.rag.reranking.reranker import cross_encoder_lite_score, rerank
from src.rag.retrieval.retriever import (
    Retriever,
    fuse_scores,
    keyword_score,
    recency_score,
    source_score,
)
from src.rag.retrieval.store import MemoryVectorStore
from src.rag.service import RagService


def _news(
    i: int, title: str, body: str, source: str = "cafef", days_ago: int = 1
) -> dict[str, object]:
    return {
        "id": i,
        "title": title,
        "content": body,
        "source": source,
        "symbol": "FPT",
        "published_at": datetime.now(tz=UTC) - timedelta(days=days_ago),
    }


class TestHashEmbedding:
    def test_deterministic(self) -> None:
        m = HashEmbedding(dim=64)
        assert m.embed("FPT lợi nhuận tăng") == m.embed("FPT lợi nhuận tăng")

    def test_normalized(self) -> None:
        import math

        v = HashEmbedding(dim=32).embed("ngân hàng tăng trưởng tín dụng")
        assert abs(math.sqrt(sum(x * x for x in v)) - 1.0) < 1e-9

    def test_empty_is_zero(self) -> None:
        assert HashEmbedding(dim=16).embed("") == [0.0] * 16

    def test_similar_beats_noise(self) -> None:
        m = HashEmbedding()
        q = m.embed("FPT lợi nhuận quý 3 tăng mạnh")
        same = m.embed("FPT lợi nhuận quý 3 tăng mạnh mẽ")
        other = m.embed("thời tiết hôm nay nắng đẹp")
        assert cosine_similarity(q, same) > cosine_similarity(q, other)

    def test_tokenize_vietnamese(self) -> None:
        assert "fpt" in tokenize("FPT Lợi-Nhuận 2026!")


class TestChunking:
    def test_single_short_doc(self) -> None:
        chunks = chunk_text("Tin ngắn.", doc_id="d1", title="T", source="cafef")
        assert len(chunks) == 1
        assert chunks[0].chunk_id == "d1#c0"
        assert chunks[0].source == "cafef"

    def test_long_splits_with_overlap(self) -> None:
        body = "\n\n".join(
            f"Đoạn {i} " + ("nội dung thị trường " * 40) for i in range(5)
        )
        chunks = chunk_text(body, doc_id="d2", max_chars=400, overlap_chars=50)
        assert len(chunks) >= 3
        assert all(c.doc_id == "d2" for c in chunks)

    def test_empty_returns_none(self) -> None:
        assert chunk_text("   ", doc_id="d3") == []

    def test_symbol_uppercased(self) -> None:
        chunks = chunk_text("x", doc_id="d4", symbol="fpt")
        assert chunks[0].symbol == "FPT"

    def test_news_item(self) -> None:
        chunks = chunk_news_item(_news(7, "T", "Nội dung tin FPT"))
        assert chunks and chunks[0].doc_type == "news"


class TestRetrieval:
    def _seeded(self) -> tuple[Retriever, MemoryVectorStore]:
        emb = HashEmbedding()
        store = MemoryVectorStore(emb)
        items = [
            _news(1, "FPT lợi nhuận quý 3 tăng mạnh",
                  "FPT công bố lợi nhuận quý 3 tăng 25% nhờ mảng công nghệ",
                  days_ago=1),
            _news(2, "VCB tín dụng tăng trưởng",
                  "Vietcombank mở rộng tín dụng bán lẻ trong quý 3",
                  days_ago=2),
            _news(3, "Thời tiết Hà Nội",
                  "Dự báo thời tiết Hà Nội nắng đẹp cả tuần", days_ago=1),
        ]
        store.upsert([c for it in items for c in chunk_news_item(it)])
        return Retriever(store, emb), store

    def test_relevant_ranks_first(self) -> None:
        ret, _ = self._seeded()
        docs = ret.retrieve("FPT lợi nhuận quý 3", top_k=3)
        assert docs[0].chunk.title.startswith("FPT")
        assert docs[0].final_score >= docs[-1].final_score

    def test_symbol_filter(self) -> None:
        ret, _ = self._seeded()
        docs = ret.retrieve("quý 3", top_k=5, symbol="FPT")
        assert docs and all(d.chunk.symbol == "FPT" for d in docs)

    def test_scores_in_range(self) -> None:
        ret, _ = self._seeded()
        for d in ret.retrieve("tín dụng", top_k=3):
            for s in (d.vector_score, d.keyword_score,
                      d.recency_score, d.source_score):
                assert 0.0 <= s <= 1.0 + 1e-9

    def test_keyword_and_recency(self) -> None:
        assert keyword_score("FPT lợi nhuận", "FPT lợi nhuận tăng") > 0.5
        assert keyword_score("FPT", "thời tiết") == 0.0
        fresh = recency_score(datetime.now(tz=UTC))
        stale = recency_score(datetime.now(tz=UTC) - timedelta(days=365))
        assert fresh > stale
        assert source_score("cafef") > source_score("blog-lạ")

    def test_fuse_math(self) -> None:
        assert fuse_scores(1.0, 1.0, 1.0, 1.0) == 1.0
        assert fuse_scores(0.0, 0.0, 0.0, 0.0) == 0.0

    def test_empty_query(self) -> None:
        ret, _ = self._seeded()
        assert ret.retrieve("", top_k=5) is not None


class TestRerank:
    def test_exact_phrase_boost(self) -> None:
        emb = HashEmbedding()
        store = MemoryVectorStore(emb)
        store.upsert([c for c in chunk_news_item(_news(
            1, "FPT lợi nhuận", "FPT lợi nhuận quý 3 tăng mạnh mẽ liên tục"))])
        store.upsert([c for c in chunk_news_item(_news(
            2, "FPT chung chung", "FPT là công ty công nghệ thông tin"))])
        ret = Retriever(store, emb)
        docs = ret.retrieve("FPT lợi nhuận quý 3 tăng", top_k=2)
        order_before = [d.chunk.doc_id for d in docs]
        after = rerank("FPT lợi nhuận quý 3 tăng", docs)
        assert {d.chunk.doc_id for d in after} == set(order_before)
        assert cross_encoder_lite_score(
            "a b", "a b c") >= cross_encoder_lite_score("a b", "x y z")


class TestEvidence:
    def test_build_and_shape(self) -> None:
        svc = RagService()
        svc.ingest_news_items([_news(1, "FPT tăng", "FPT lợi nhuận tăng mạnh")])
        evs = svc.evidence_for("FPT lợi nhuận", top_k=2)
        assert evs
        d = evidence_to_dict(evs[0])
        for k in ("claim", "source", "source_type", "evidence", "confidence",
                  "doc_id", "chunk_id", "symbol"):
            assert k in d
        assert 0.0 <= d["confidence"] <= 1.0  # type: ignore[operator]
        assert confidence_for.__name__ == "confidence_for"
        assert build_evidence([], []) == []


class TestRagService:
    def test_ingest_search_status(self) -> None:
        svc = RagService()
        res = svc.ingest_news_items([
            _news(1, "FPT lợi nhuận", "FPT lợi nhuận quý 3 tăng"),
            _news(2, "VCB tín dụng", "Vietcombank tín dụng bán lẻ tăng"),
        ])
        assert res["docs"] == 2 and res["chunks"] >= 2
        assert svc.size >= 2
        docs = svc.search("FPT lợi nhuận", top_k=2)
        assert docs and docs[0].final_score >= 0
        st = svc.status()
        assert st["chunks"] >= 2 and "model" in st

    def test_symbol_scoped(self) -> None:
        svc = RagService()
        svc.ingest_news_items([_news(1, "T", "FPT tăng trưởng", days_ago=1)])
        assert svc.search("tăng trưởng", top_k=3, symbol="FPT")

        chunks = chunk_news_item(_news(7, "T", "Nội dung tin FPT"))
        assert chunks and chunks[0].doc_type == "news"


class TestQdrantMirrorIdentity:
    """Qdrant point ids must be process-stable (never Python's randomized hash)."""

    def test_stable_point_id_is_deterministic_and_positive(self) -> None:
        from src.rag.retrieval.store import stable_point_id

        first = stable_point_id("news:42#c0")
        assert first == stable_point_id("news:42#c0")
        assert 0 <= first < 2**63
        assert stable_point_id("news:42#c1") != first

    def test_stable_point_id_survives_pythonhashseed(self) -> None:
        import os
        import subprocess
        import sys
        from pathlib import Path

        code = (
            "from src.rag.retrieval.store import stable_point_id\n"
            "print(stable_point_id('news:42#c0'))\n"
        )
        repo = Path(__file__).resolve().parents[2]
        outs = []
        for seed in ("1", "2"):
            proc = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                check=True,
                cwd=repo,
                env={**os.environ, "PYTHONHASHSEED": seed},
            )
            outs.append(proc.stdout.strip())
        assert outs[0] == outs[1]

    def test_vectors_for_matches_stored_embeddings(self) -> None:
        embedder = HashEmbedding(dim=16)
        store = MemoryVectorStore(embedder)
        chunks = chunk_text("FPT tăng trưởng lợi nhuận", doc_id="news:1")
        store.upsert(chunks)
        assert store.vectors_for(chunks) == [embedder.embed(c.text) for c in chunks]

