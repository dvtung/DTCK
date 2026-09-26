# Bộ nhớ dự án — Sự cố đã biết (Bản tiếng Việt)

> Thuật ngữ chuyên môn (tên bảng, biến môi trường, lệnh, đường dẫn) giữ nguyên tiếng Anh.

| ID | Mảng | Vấn đề | Trạng thái | Ghi chú |
|---|---|---|---|---|
| KI-001 | Dữ liệu | Chưa chọn nguồn dữ liệu cho EOD OHLCV, báo cáo tài chính, tin tức VN | **ĐÃ GIẢI (thiết kế)** | T002 đã chọn provider (`docs/DATA_SOURCES_vi.md`, `configs/sources.yaml`); FiniPro = chính, VNDirect/TCBS/DSC dự phòng, SBV/GSO/IMF-WB vĩ mô, CafeF/VnExpress/Vietstock tin tức |
| KI-006 | Dữ liệu | URL endpoint / lược đồ response / giới hạn tần suất của provider chưa kiểm chứng (không có egress mạng khi làm T002) | ĐANG MỞ (phần lớn đã mở) | **SSI FastConnect `VERIFIED_2026-09-27`** (`Market/AccessToken` + `Market/DailyOhlc` 68 dòng + `Market/DailyIndex` 34 dòng), **Yahoo chart + CaféF RSS `VERIFIED_2026-09-25`**; còn VNDirect/TCBS/DSC/WSJ và endpoint cơ bản/sự kiện của SSI; xem `docs/DATA_SOURCES_vi.md` §8 |
| KI-007 | Dữ liệu | Chưa có chứng thực provider (`FINIPRO_ACCESS_TOKEN`… còn trống) | **ĐÃ ĐÓNG PHẦN THỊ TRƯỜNG (2026-09-27)** | Credential SSI consumer (`SSI_CONSUMER_ID`/`SSI_CONSUMER_SECRET`) chạy thật; `FINIPRO_ACCESS_TOKEN` có thể để trống vì provider tự đổi JWT. Còn chờ endpoint cơ bản/sự kiện của SSI, Vietstock, TradingEconomics |
| KI-002 | Hạ tầng | Python cục bộ là 3.14.4 — các ghim phụ thuộc (SQLAlchemy/Timescale, LangGraph…) phải kiểm chứng trên đó; image Docker dùng phiên bản ghim thay thế | ĐÃ KIỂM CHỨNG MỘT PHẦN | Phụ thuộc CSDL (SQLAlchemy 2.0.52, Alembic 1.20, psycopg 3.3) đã chạy trên 3.14; ngăn xếp ML/LLM nặng vẫn chưa kiểm chứng |
| KI-003 | Tài liệu | `docs/DATABASE_SCHEMA.md` §19 mục mở: chi tiết chính sách điều chỉnh lưỡng thời, định dạng đường dẫn object storage, retention/compression theo hypertable | ĐANG MỞ | Thiết kế đã triển khai; các mục §19 không chặn schema/migration |
| KI-004 | Hạ tầng | Dịch vụ Docker đã thực sự chạy/kiểm chứng end-to-end | ĐÃ GIẢI | Ngăn xếp `docker compose` chạy & khỏe mạnh; migration + seed đã kiểm chứng với TimescaleDB đang chạy (2026-09-13) |
| KI-005 | Repo | Các tệp đặc tả gốc đã được sao chép vào `docs/` — bản gốc vẫn ở gốc repo; phải giữ đồng bộ tới khi quyết định xoá | ĐANG MỞ | Cần quyết định giữ một bản chuẩn ở gốc hay trong `docs/` |
| KI-008 | API | Đường đọc đã phục vụ TimescaleDB qua `DbMarketService` khi `MARKET_DATA_SOURCE=db\|auto` (2026-09-25). Còn mở: mặc định vẫn là `memory`, API chưa có đường **ghi** (`POST /backtests`), và các bảng index/cơ bản chưa có job ghi | **MỘT PHẦN** (thiết kế đọc) | Hợp đồng router đã chốt; thay service bằng repository SQLAlchemy không cần đụng router. Không chặn gì cho tới khi tầng lưu trữ lên thật |
| KI-009 | Backtest | Engine T009 chỉ kiểm chứng trên **chuỗi giá tổng hợp/fixture** — chưa nạp lịch sử thị trường VN thật | ĐANG MỞ (một phần) | **Đã có dữ liệu thật** (Yahoo EOD, 2026-09-25) nhưng cửa sổ còn ngắn (~1 tháng cho FPT/VCB/HPG/ACB); backfill dài hơn khi cần kết quả có ý nghĩa thống kê |
| KI-010 | Dashboard | Dashboard T011 hiển thị **dữ liệu tổng hợp trong bộ nhớ** cho tới khi TimescaleDB + dữ liệu thật được nối | ĐÃ GIẢI (đọc) | Đã nối: `client.py` mở phong bì phân trang của API thật, thêm trang "Tin tức & RAG"; khi `MARKET_DATA_SOURCE=db\|auto` và `prices` có dòng thì dashboard hiển thị dữ liệu CSDL |
| KI-011 | RAG | Chỉ mục RAG T012 từng được dựng từ **tin tổng hợp trong bộ nhớ**; `qdrant_client` chưa cài nên vector store trong bộ nhớ là mặc định, Qdrant chỉ là mirror best-effort | ĐÃ GIẢI (phần Qdrant) | **Đóng phần client (2026-09-27):** image api/worker cài extra `[qdrant]` (chỉ `qdrant-client`, không có torch) ⇒ mirror collection `dtck_docs` chạy thật, `/readyz` báo `qdrant: up`. Trước đó: đã nạp 50 bài CaféF thật (2026-09-24/25) và liên kết mã (`news_symbols`), `/rag/search` + `/evidence` kiểm chứng trực tiếp. Baseline in-memory vẫn là đường lui khi Qdrant tắt (không crash) |
| KI-012 | ML | Fixture thị trường tổng hợp tăng đơn điệu → 100% nhãn 5 ngày dương → không thể fit classifier thật; `train-model` báo lỗi to và dừng thay vì đăng ký model giả | **ĐANG MỞ** (có lối mở) | Lối mở: dùng `DbMarketService` làm nguồn cho `train-model` — CSDL đã có nhãn hỗn hợp (ví dụ FPT 68 dương / 72 âm) và `factor_scores`; xem `memory-bank/tasks_vi.md` |

---

## Nguyên tắc làm việc

- Mục nào đánh dấu ĐANG MỞ chỉ chặn công việc phía sau khi nó được liệt kê như một phụ thuộc.
- Không bao giờ đóng một sự cố mà không ghi rõ ai đã kiểm chứng bản sửa và khi nào.
