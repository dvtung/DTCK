# DTCK — Nền tảng Nghiên cứu & Quyết định Đầu tư AI

> **AI không thay thế nhận định đầu tư. AI gia tăng tốc độ, tính nhất quán, chiều sâu và khả năng truy vết của hoạt động nghiên cứu đầu tư.**

Nền tảng nghiên cứu & hỗ trợ quyết định ứng dụng AI cho **thị trường chứng khoán Việt Nam** (HOSE / HNX / UPCOM), khởi đầu với danh mục VN30.

**⚠️ Không phải hệ thống giao dịch tự động.** Nền tảng tạo ra *nghiên cứu, điểm số và đánh giá rủi ro có bằng chứng xác thực* — con người luôn là người đưa ra quyết định đầu tư cuối cùng (spec §4.6).

---

## Chuỗi xử lý (Pipeline)

```text
DỮ LIỆU → QUANT → BACKTEST → ML → RAG → AI AGENT → BẰNG CHỨNG → KIỂM SOÁT RỦI RO → CON NGƯỜI
```

Nguyên tắc cốt lõi (spec §4): **Dữ liệu là trên hết** · **Tính toán tất định trước** (LLM không bao giờ tự tính RSI/P/E/ROE/…) · **LLM là tầng suy luận** · **Suy luận dựa trên bằng chứng**. Mọi chiến lược phải được **kiểm nghiệm lịch sử (backtest) trước khi triển khai**.

---

## Cấu trúc thư mục repository (spec §35)

```text
apps/          api (FastAPI) · dashboard (Streamlit) · worker (schedulers/ingest)
src/           data · market · quant · ml · rag · agents · evidence · portfolio · backtesting · common
database/      alembic migrations + seeds
tests/         unit · integration · data_quality · agent · e2e
docs/          kiến trúc & đặc tả kỹ thuật
memory-bank/   bộ nhớ dự án xuyên phiên (§37)
helper/        hướng dẫn vận hành (triển khai, tài nguyên)
notebooks/     nghiên cứu & thử nghiệm
configs/       cấu hình hệ thống
scripts/       script vận hành
offline_package/  wheel offline cho cài đặt air-gapped
docker/        Dockerfiles + compose
```

## Tài liệu kỹ thuật

| Tài liệu | Nội dung |
|---|---|
| `docs/SYSTEM_SPECIFICATION.md` | **Đặc tả hệ thống** (v1.0, 58 mục) — đọc tài liệu này đầu tiên |
| `docs/AI_INVESTMENT_CONCEPT.md` | Bản thảo khái niệm ban đầu (tiếng Việt) |
| `docs/ARCHITECTURE_vi.md` | Kiến trúc logic, các thành phần, giai đoạn, tiêu chí MVP |
| `docs/DATABASE_SCHEMA_vi.md` | Toàn bộ lược đồ CSDL PostgreSQL/TimescaleDB |
| `docs/DATA_ARCHITECTURE_vi.md` | Miền dữ liệu, luồng nạp, khung chất lượng dữ liệu |
| `docs/QUANT_ENGINE_vi.md` | Bộ tính toán nhân tố và chấm điểm tất định |
| `docs/BACKTESTING_vi.md` | Quy trình backtest, phòng tránh thiên kiến, chỉ số đo lường |
| `docs/ML_ARCHITECTURE_vi.md` | Quy trình XGBoost/LightGBM, registry model, hiệu chuẩn |
| `docs/RAG_ARCHITECTURE_vi.md` | Nạp Qdrant + truy xuất lai (hybrid) + bằng chứng xác thực |
| `docs/AGENT_ARCHITECTURE_vi.md` | Agent LangGraph, công cụ, đầu ra có cấu trúc |
| `docs/API_SPECIFICATION_vi.md` | Nhóm API REST `/api/v1/*` |
| `docs/DATA_SOURCES_vi.md` | Thiết kế nguồn dữ liệu & kế hoạch chứng thực (T002) |
| `docs/DEPLOYMENT_vi.md` | Cài đặt & triển khai hệ thống |
| `docs/SECURITY_vi.md` | Quản lý secret, xác thực, kiểm toán, phân quyền RBAC |
| `memory-bank/` | Bộ nhớ dự án (§37): ngữ cảnh, hiện trạng, quyết định, vấn đề, công việc, changelog |

## Bắt đầu nhanh (MVP)

```bash
cp .env.example .env        # điền các giá trị thực tế
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api python -m database.seeds.run_all
```

- API docs → http://localhost:8000/docs
- Dashboard → http://localhost:8501

Xem `docs/DEPLOYMENT_vi.md` và `helper/deployment_vi.md` để biết thêm chi tiết.

## Lộ trình phát triển (spec §57)

**Đặc tả (100%) → Thiết kế CSDL → Cấu trúc Repo → Nguồn dữ liệu → Nạp dữ liệu → Quant Engine → Backtest → RAG → AI Agent → ML → Danh mục → Vận hành Production**

> **Không chuyển sang Agent trước khi Data + Quant + Backtest đạt baseline có thể kiểm chứng.**

## Trạng thái hiện tại

Xem `memory-bank/current-state_vi.md` và `memory-bank/tasks_vi.md`.
