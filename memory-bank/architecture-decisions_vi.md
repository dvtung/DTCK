# Bộ nhớ dự án — Hồ sơ quyết định kiến trúc (Bản tiếng Việt)

> Thuật ngữ chuyên môn (tên bảng, biến môi trường, lệnh, đường dẫn) giữ nguyên tiếng Anh.

**Các ADR ghi từ đặc tả §53 (ADR-001 … ADR-007). Trạng thái: ĐÃ ĐƯỢC ĐẶC TẢ CHẤP NHẬN.**

| ADR | Quyết định | Lý do |
|---|---|---|
| **ADR-001** | Tách phép tính định lượng khỏi LLM | Tất định, kiểm thử được, tái lập được |
| **ADR-002** | Qdrant là CSDL vector ban đầu | Phù hợp RAG tài liệu/tin tức; khớp kiến trúc tìm kiếm vector sẵn có |
| **ADR-003** | PostgreSQL/TimescaleDB là kho dữ liệu cấu trúc chính | Giảm độ phức tạp hạ tầng trong MVP |
| **ADR-004** | Hoãn Kafka/Airflow | Hạ tầng mở rộng theo tải thực tế |
| **ADR-005** | Trừu tượng hoá provider LLM | Tránh bị khoá vào một nhà cung cấp |
| **ADR-006** | Output AI dùng lược đồ có cấu trúc (Pydantic) | Kiểm chứng, lưu trữ, tích hợp API, tái lập được |
| **ADR-007** | Backtesting là thành phần hạng nhất | Tín hiệu đầu tư phải được kiểm chứng thực nghiệm |

---

## Đề xuất hoãn cho ADR tương lai

- Chính sách nén/lưu trữ TimescaleDB theo từng hypertable (chờ khối lượng thật).
- Bố cục lưu trữ đối tượng (tương thích S3) cho tài liệu thô/sản phẩm backtest.
- Chi tiết cơ chế xác thực API (JWT so với chỉ API-key) — quyết ở giai đoạn Production.
- Lựa chọn task queue (Redis/Celery so với tập worker thuần) — giai đoạn Production.
