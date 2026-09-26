# KIẾN TRÚC RAG (Bản tiếng Việt)

## Nền tảng Nghiên cứu & Quyết định Đầu tư AI

> Thuật ngữ chuyên môn (tên bảng, API, mã nguồn) giữ nguyên tiếng Anh.

**Phiên bản:** 1.0
**Trạng thái:** Cơ sở — suy ra từ SYSTEM_SPECIFICATION.md v1.0 (§18)

---

# 1. Mục đích

Xây kho tri thức có bằng chứng trên tài liệu thị trường tiếng Việt để agent lập luận với nguồn trích dẫn kiểm chứng được (§4.4, §19).

---

# 2. Kho tài liệu (§18.1)

```text
Tin tức
Báo cáo tài chính
Công bố thông tin doanh nghiệp
Báo cáo thường niên
Báo cáo quý
Báo cáo phân tích
Thông tin doanh nghiệp
```

---

# 3. Luồng nạp (Ingestion Pipeline)

```text
Tài liệu (PDF/HTML/text)
  ↓ chunking (nhận biết cấu trúc: mục, bảng, tiêu đề)
  ↓ trích metadata (mã, ngành, loại sự kiện, ngày, nguồn)
  ↓ embedding (trừu tượng hóa provider — ADR-005)
  ↓ upsert vào Qdrant (payload = metadata; vector = embedding)
  ↓ đăng ký dòng metadata trong bảng documents / news (DB)
```

- Giữ provenance tới từng chunk (tiêu đề, nguồn, published_at, mã).
- Qdrant + metadata PostgreSQL liên kết qua `qdrant_point_id`.

---

# 4. Luồng truy xuất (§18.2)

```text
Câu hỏi người dùng
    ↓
Lọc metadata       (mã, ngành, khoảng ngày, loại tài liệu, nguồn)
    ↓
Tìm vector         (ngữ nghĩa dense)
    ↓
Tìm từ khóa        (BM25 trên bảng news/documents)
    ↓
Trọng số gần đây
    ↓
Độ tin cậy nguồn
    ↓
Reranking
    ↓
Tập bằng chứng     (top-k kèm điểm)
```

Kết hợp lai (hybrid fusion) = điểm dense + sparse (BM25), rồi reranker (cross-encoder hoặc API rerank của provider).

> Trạng thái triển khai 2026-09-25: `HashEmbedding` tất định + `MemoryVectorStore` in-memory là baseline; adaptor Qdrant best-effort; đã nạp 50 bài CaféF thật, kiểm chứng `/rag/search` + `/evidence`.

---

# 5. Thành phần bổ trợ

- **Dịch vụ embedding** (`src/rag/embedding`) — trừu tượng hóa provider (tương thích OpenAI, local, …), phiên bản hóa model embedding.
- **Retriever** (`src/rag/retrieval`) — truy xuất lai + lọc metadata.
- **Reranker** (`src/rag/reranking`) — cross-encoder tùy chọn.
- **Bộ dựng tập bằng chứng** (`src/evidence`) — biến top-k kết quả thành đối tượng `Evidence` (§19).

---

# 6. Đối tượng bằng chứng (§19)

```json
{
  "claim": "...",
  "source": "...",
  "source_type": "financial_report",
  "published_at": "...",
  "data_timestamp": "...",
  "evidence": "...",
  "confidence": 0.91
}
```

Evidence liên kết tới: Analysis, Prediction, Agent run, Report (đa hình qua `linked_entity_type/id`).

---

# 7. Đánh giá

- Chất lượng truy xuất: hit rate @k, MRR, NDCG trên bộ câu hỏi có nhãn.
- Kiểm ảo giác agent: mọi khẳng định thực tế trong output agent phải ánh xạ tới một mục Evidence (§38 đánh giá agent).
- Thiên vị gần đây (freshness bias): trọng số recency phải ngăn tài liệu cũ-nhưng-giống-ngữ nghĩa lấn át tin mới.

---

# 8. Cấu hình Collection Qdrant

- Khoảng cách: Cosine
- Vector: theo tên model embedding (collection đa vector nếu cần)
- Index payload: `symbol`, `published_at`, `source`, `doc_type`
