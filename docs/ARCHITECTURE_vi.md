# KIẾN TRÚC HỆ THỐNG (Bản tiếng Việt)

## Nền tảng Nghiên cứu & Quyết định Đầu tư AI

> Thuật ngữ chuyên môn (tên bảng, API, mã nguồn) giữ nguyên tiếng Anh.

**Phiên bản:** 1.0
**Trạng thái:** Cơ sở — suy ra từ SYSTEM_SPECIFICATION.md v1.0 (§7)

---

# 1. Triết lý hệ thống

```text
                  ┌──────────────┐
                  │    DATA      │  DỮ LIỆU
                  └──────┬───────┘
                         ↓
                  ┌──────────────┐
                  │    QUANT     │  ĐỊNH LƯỢNG
                  └──────┬───────┘
                         ↓
                  ┌──────────────┐
                  │   BACKTEST   │  KIỂM THỬ NGƯỢC
                  └──────┬───────┘
                         ↓
                  ┌──────────────┐
                  │     ML       │  HỌC MÁY
                  └──────┬───────┘
                         ↓
                  ┌──────────────┐
                  │     RAG      │  TRI THỨC
                  └──────┬───────┘
                         ↓
                  ┌──────────────┐
                  │  AI AGENT    │  TÁC TỬ AI
                  └──────┬───────┘
                         ↓
                  ┌──────────────┐
                  │  EVIDENCE    │  BẰNG CHỨNG
                  └──────┬───────┘
                         ↓
                  ┌──────────────┐
                  │ RISK CONTROL │  KIỂM SOÁT RỦI RO
                  └──────┬───────┘
                         ↓
                  ┌──────────────┐
                  │    HUMAN     │  CON NGƯỜI
                  └──────────────┘
```

Nguyên tắc lõi (đặc tả §56):

> **AI không thay thế phán đoán đầu tư. AI tăng tốc độ, tính nhất quán, chiều sâu và khả năng truy vết của nghiên cứu đầu tư.**

Bốn nguyên tắc thiết kế ràng buộc (§4):

1. **Dữ liệu trước** — dữ liệu xấu → đặc trưng xấu → model xấu → agent xấu. Cổng chất lượng dữ liệu quyết định việc dùng.
2. **Tính toán tất định trước** — mọi phép tính tài chính/quant (RSI, P/E, ROE, …) chạy trong engine phần mềm, không bao giờ trong LLM.
3. **LLM là tầng lập luận** — LLM lập kế hoạch, chọn tool, tổng hợp, diễn giải; **không phải** nguồn chân lý và không bao giờ được bịa số liệu tài chính.
4. **Lập luận dựa trên bằng chứng** — mọi khẳng định → bằng chứng → nguồn → timestamp → phiên bản dữ liệu (§19).

Thêm: Backtest trước khi triển khai (§4.5), Con người trong vòng lặp (§4.6), Kiểm toán đầy đủ (§4.7).
# 2. Kiến trúc logic (§7.1)

```text
┌───────────────────────────────────────────────┐
│                 NGUỒN DỮ LIỆU                │
│                                               │
│ Thị trường │ Tài chính │ Tin tức │ Vĩ mô │ Sự kiện │
└───────────────────────┬───────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│              NẠP DỮ LIỆU                      │
│                                               │
│ API / ETL / Collector / Scheduler             │
└───────────────────────┬───────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│              NỀN TẢNG DỮ LIỆU                 │
│                                               │
│ Thô │ Sạch │ Tuyển chọn │ Đặc trưng │ Tài liệu │
└──────────────┬───────────────────────┬────────┘
               │                       │
               ▼                       ▼
       ┌───────────────┐       ┌──────────────┐
       │ QUANT ENGINE  │       │ RAG ENGINE   │
       │ (định lượng)  │       │ (tri thức)   │
       └───────┬───────┘       └──────┬───────┘
               │                       │
               ▼                       ▼
       ┌───────────────┐       ┌──────────────┐
       │ ML ENGINE     │       │ AGENT +      │
       │ (học máy)     │       │ EVIDENCE     │
       └───────┬───────┘       └──────┬───────┘
               │                       │
               └───────────┬───────────┘
                           ▼
               ┌───────────────────────┐
               │ DASHBOARD + CẢNH BÁO  │
               │ + CON NGƯỜI QUYẾT ĐỊNH│
               └───────────────────────┘
```

---

# 3. Ranh giới dịch vụ

- **Data Service:** nạp, kiểm tra, chuẩn hóa, lưu trữ (PostgreSQL + TimescaleDB, Qdrant cho vector).
- **Quant Service:** chỉ báo, hệ số, chấm điểm — tất định, không LLM.
- **ML Service:** dataset đặc trưng, huấn luyện, hiệu chuẩn, registry, dự báo.
- **RAG Service:** chunking, embedding, truy xuất lai, rerank, tập bằng chứng.
- **Agent Service:** 4 agent + orchestrator, gọi tool, audit đầy đủ.
- **API Service (FastAPI):** biên REST `/api/v1/*` cho mọi consumer (dashboard, agent, ngoài).
- **Dashboard (Streamlit):** tổng quan, sàng lọc, xếp hạng, chi tiết mã, backtest, tin tức & RAG, 📧 Quản lý Email (T018), sức khỏe hệ thống.

---

# 4. Kiến trúc Tool (§22)

LLM không bao giờ chạm trực tiếp CSDL. Đi qua tầng dịch vụ ứng dụng:

```text
LLM
 ↓
Gọi tool
 ↓
Dịch vụ ứng dụng
 ↓
CSDL / Quant Engine / RAG
 ↓
Kết quả có cấu trúc
 ↓
LLM
```

Danh mục tool (MVP): `get_stock_price`, `get_technical`, `get_fundamentals`, `get_valuation`, `get_peer_analysis`, `get_market_regime`, `get_news`, `get_corporate_events`, `get_prediction`, `get_risk`.

---

# 5. Topo runtime

## MVP (Docker Compose) — §33

```text
┌──────────────────────────┐
│ FastAPI                  │
├──────────────────────────┤
│ Worker (scheduler/ingest)│
├──────────────────────────┤
│ PostgreSQL (TimescaleDB) │
├──────────────────────────┤
│ Qdrant                   │
├──────────────────────────┤
│ Streamlit (dashboard)    │
└──────────────────────────┘
```

## Production (tương lai)

```text
Load Balancer → FastAPI → Task Queue → Workers → PostgreSQL/TimescaleDB → Qdrant → Object Storage
```

---

# 6. Bố cục repo (§35)

```text
apps/       api (FastAPI), dashboard (Streamlit), worker (schedulers/ingest)
src/        data, market (technical/fundamental/valuation/momentum/risk), quant,
            ml, rag, agents, evidence, portfolio, backtesting, common
database/   migration alembic + seed
tests/      unit, integration, data_quality, agent, e2e
notebooks/  nghiên cứu & thử nghiệm
configs/    file môi trường/cấu hình
scripts/    script vận hành
docs/       tài liệu kiến trúc (+ bản tiếng Việt *_vi.md)
memory-bank/ bộ nhớ dự án xuyên phiên
offline_package/ wheel offline cài đặt air-gapped
docker/     Dockerfile + compose
```

---

# 7. Bề mặt API (§28)

```text
/api/v1/market
/api/v1/stocks
/api/v1/fundamentals
/api/v1/technical
/api/v1/valuation
/api/v1/news
/api/v1/analysis
/api/v1/predictions
/api/v1/portfolio
/api/v1/backtests
/api/v1/agents
```

Xem `docs/API_SPECIFICATION.md` (bản Việt: `docs/API_SPECIFICATION_vi.md`).

---

# 8. Giai đoạn phát triển & Cổng MVP (§48–§52)

| Phase | Sản phẩm | MVP |
|---|---|---|
| 0 — Đặc tả | SYSTEM_SPECIFICATION, ARCHITECTURE, DATABASE_SCHEMA | — |
| 1 — Nền tảng dữ liệu | PostgreSQL, dữ liệu thị trường/lịch sử, kiểm chứng, pipeline | một phần MVP-1 |
| 2 — Quant Engine | engine kỹ thuật/cơ bản/định giá/rủi ro/hệ số/chấm điểm | MVP-1 |
| 3 — Backtesting | walk-forward, chi phí giao dịch, báo cáo hiệu quả | MVP-1 |
| 4 — RAG | nạp, embedding, Qdrant, truy xuất lai, reranking | MVP-2 |
| 5 — AI Agent | 4 agent + orchestrator | MVP-2 |
| 6 — ML | dataset đặc trưng, XGBoost/LightGBM, hiệu chuẩn, registry | MVP-3 |
| 7 — Production | FastAPI, dashboard, auth, monitoring, alert, audit, Docker, CI/CD | Production |

**MVP-1 KHÔNG cần LLM Agent.** Đặc tả (§49) nói rõ: data → quant → score → ranking → backtest → dashboard.

---

# 9. Mối quan tâm xuyên suốt

- **Quan sát được (§46):** CPU/bộ nhớ/đĩa/DB/độ trễ API/trạng thái worker/độ trễ & chi phí LLM/lỗi agent/lỗi pipeline/hiệu quả model/độ tươi dữ liệu.
- **Kiểm soát chi phí (§47):** LLM không bao giờ dùng cho task tất định; tối thiểu số gọi LLM, tối đa giá trị thông tin.
- **Bảo mật (§32):** auth API, quản lý secret, RBAC, audit log; không key/mật khẩu/secret trong mã nguồn, git hay Docker image. Xem `docs/SECURITY.md` (bản Việt: `docs/SECURITY_vi.md`).
- **Quản trị Model & Agent (§40–§41):** registry, trạng thái, hành động cấm tuyệt đối của agent.
