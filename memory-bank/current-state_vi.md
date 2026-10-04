# Bộ nhớ dự án — Hiện trạng (Bản tiếng Việt)

> Thuật ngữ chuyên môn (tên bảng, biến môi trường, lệnh, đường dẫn) giữ nguyên tiếng Anh.

**Cập nhật lần cuối:** 2026-10-04

---

## 1. Trạng thái theo đặc tả §58

```text
Đặc tả:         ████████████████████ 100%   (docs/SYSTEM_SPECIFICATION.md, v1.0)
Kiến trúc:      ████████████████████ 100%   (docs/ARCHITECTURE.md đã soạn)
CSDL:           ████████████████████ 100%   (lược đồ 44 bảng + migration 0005_strategy_scoring + hypertable + seed XONG; 218.736 bars prices 2020-2026)
Pipeline dữ liệu:████████████████████ 100%   (T004+T005 XONG + chuỗi thật [ssix_finipro,yahoo,vndirect,tcbs,dsc]; backfill 2020-2026 hoàn tất)
Quant Engine:   ████████████████████ 100%   (T006+T007+T008+T019 XONG: compute-scores + chấm điểm 3 chiến lược 24 chỉ tiêu)
Backtesting:    ████████████████████ 100%   (T009 + chiều ghi CSDL + form Backtest trên dashboard + backtest 3 chiến lược)
API:            ████████████████████ 100%   (T010+T016+T018+T019: 14 tệp router, 52 đường dẫn / 57 thao tác; /readyz dò thật, market_source=auto->db)
Dashboard:      ████████████████████ 100%   (T011+T015c+T016+T018+T020+T021: 10 trang gồm Chấm điểm chiến lược, nến VNINDEX 9 khung thời gian, delta điểm số, Tin tức & RAG, Quản lý Email, Lịch sử Worker)
RAG:            ████████████████████ 100%   (T012 + 50 bài CaféF thật + mirror collection dtck_docs, qdrant: up)
Tác tử AI:      ████████████████████ 100%   (T013 + T016 nối LLM local Ollama qwen3.5; agents: llm:qwen3.5)
ML:             ████████████████████ 100%   (T014 + T015b + T020: registry lưu CSDL + huấn luyện lại trên tập lịch sử 2020-2026; model price_direction_xgb@1.0.0)
Production:     ████████████████████ 100%   (scheduler 9 job gồm chấm điểm chiến lược 17:00 + JWT/RBAC + /metrics + CI/CD + sao lưu/phục hồi)
Thông báo email:████████████████████ 100%   (T018+T022: 4 bảng, email tự động 08:00/12:30/16:30 kèm Top 10 3 chiến lược, cột giá hiện tại, KPI điểm số VNINDEX)
```

---

## 2. Hiện có gì (khung Phase-0 hoàn tất + thiết kế CSDL BƯỚC 2 đã triển khai)

- **Cấu trúc repo** đã dựng đầy đủ theo đặc tả §35 (`apps/`, `src/`, `database/`, `tests/`, `notebooks/`, `configs/`, `scripts/`, `docs/`, `memory-bank/`, `offline_package/`, `docker/`).
- **Bộ tài liệu** đầy đủ (13+ tệp, danh sách ở `project-context_vi.md` §7) — toàn bộ chuẩn hóa 100% tiếng Việt, đã loại bỏ các bản tiếng Anh trùng lặp (2026-09-26).
- **Memory bank** 100% bằng tiếng Việt và là nguồn chân lý duy nhất.
- `pyproject.toml`, `.env.example`, `.gitignore`, `README.md`, `docker-compose.yml`, Dockerfile — đã tạo.
- **Model SQLAlchemy** (`src/common/models/`) triển khai mọi bảng trong `docs/DATABASE_SCHEMA_vi.md` — 44 bảng (gồm 4 bảng `notifications` T018 và 2 bảng `strategy` T019), nguồn chân lý duy nhất (`Base.metadata`).
- **Migration Alembic** `database/migrations/versions/` → head `0005_strategy_scoring`; 12 bảng chuỗi thời gian là TimescaleDB hypertable (theo §17), có `upgrade`/`downgrade`.
- **Seed** (`database/seeds/`) — exchanges (HOSE/HNX/UPCOM), 10 sector + 15 industry, universe mở rộng T016 (VN30 + VN100 + HNX/UPCOM, 138 mã). Idempotent; nối vào `database/seeds/run_all.py`.
- **Pipeline dữ liệu** (`src/data/`) — collectors, validators, normalizers, pipelines, providers (base + fixture + HTTP-JSON + registry), chấm điểm chất lượng (§39). FixtureProvider cho phép kiểm thử pipeline hoàn toàn ngoại tuyến. Worker CLI (`apps/worker/cli.py`) đã nối lệnh ingest.
- **Cột mốc dữ liệu thật (2026-09-24/25/27; cập nhật 2026-10-04)** — **`SSIFastConnectProvider` là nguồn thị trường CHÍNH** (`priority 100`) + `YahooChartProvider` dự phòng. **CSDL hiện có 218.736 dòng `prices`** (2020-01-02 → 2026-09-30, bao phủ 138 mã thuộc vũ trụ mở rộng) + 992 dòng `index_prices` (VNINDEX/VN30) + 50 bài CaféF thật + 201.402 dòng `financial_statements`.
- **Đường đọc CSDL (W1, 2026-09-25)** — protocol `MarketSource` + `DbMarketService` (13 nhóm bảng thật, cache theo request) sau `MARKET_DATA_SOURCE=memory|db|auto` (`apps/api/dependencies.py`); router không đổi, `/readyz` trả `market_source` (`<chế độ>-><service>`). Compose api/worker mặc định `auto`; code + `.env.example` mặc định `memory` để unit test không cần CSDL.
- **`/readyz` trung thực (2026-09-27)** — `apps/api/main.py` dò thật từng phụ thuộc (không hardcode): `database` (`connected`/`connected-no-prices`/`unreachable`), `qdrant` (`up`/`offline-index-ready`), `agents` (`llm:<model>` | `offline:<tasks>`) + khoá `market_source`; probe không bao giờ ném 5xx. Image api/worker cài extra `[qdrant]` nên collection `dtck_docs` được mirror thật (`qdrant: up`).
- **Scheduler worker (cập nhật 2026-10-04)** — APScheduler **9 job** (`run_scheduler`): news mỗi 15 phút, nạp EOD Thứ 2–6 11:30 + 15:30 ICT kèm `index_prices`, `daily_eod_catchup` 15:50, scoring Thứ 2–6 12:00 + 16:00 ICT, **`daily_strategy_scoring` Thứ 2–6 17:00 ICT** (T020), **báo cáo email Thứ 2–6 08:00 + 12:30 + 16:30 ICT** (T018/T022) + `email_schedule_sync` mỗi 15'; fail-soft, `max_instances=1` + `coalesce`.
- **Nối dữ liệu thật cho dashboard (cập nhật 2026-10-04)** — 10 trang: Tổng quan (nến VNINDEX 9 khung thời gian + delta điểm số), Bộ lọc 3 sàn, Xếp hạng quant, **Chấm điểm chiến lược (T021)**, Chi tiết mã, Backtests, Tin tức & RAG, Quản lý Email, Sức khỏe hệ thống, Lịch sử Worker.
- **Khung chất lượng dữ liệu** (`src/data/quality.py`) — chấm điểm 6 chiều với trung bình có trọng số, chuẩn hoá lại và cổng ngưỡng (§39).
- **Scoring engine** (`src/quant/scoring/engine.py` & `src/quant/strategy/engine.py`, T008 + T019) — `decompose_score()` đóng góp theo hệ số với trọng số chuẩn hoá lại, `score_universe()`; Chấm điểm 3 chiến lược Ngắn/Trung/Dài hạn với 24 chỉ tiêu định lượng, cổng lọc xu hướng, Red Flag, vùng mua ATR, cắt lỗ và mục tiêu chốt lời.
- **Engine backtesting** (`src/backtesting/` & `src/quant/strategy/backtest.py`, T009 + T019) — backtest cuốn chiếu, chi phí, kiểm soát thiên lệch; backtest chiến lược 3 hồ sơ.
- **REST API** (`apps/api/`, **52 đường dẫn / 57 thao tác** trên `/api/v1/*`: **14 tệp router** gồm `notifications` và `strategy`) — FastAPI với các nhóm router theo đặc tả; 26 schema Pydantic; `/healthz` + `/readyz` với `market_source=auto->db`.
- **Dashboard Streamlit** (`apps/dashboard/`, **10 trang**: AppTest 10 trang pass 100%).
- Kiểm thử **(2026-10-04):** **640+ kiểm thử đạt** (unit + integration); ruff + mypy sạch.

---

## 3. Task vừa hoàn thành & Quy ước mới

**ID:** `T022 — Cập nhật Nội dung Email Định kỳ & Lịch trình Worker 17:00 (2026-10-04)`
**Trạng thái:** HOÀN THÀNH

**Sản phẩm:**
- **KPI VNINDEX trong email**: Thay đổi từ % sang số điểm tăng/giảm (`+X.XX điểm` / `-X.XX điểm`).
- **Bảng Top 15 "Đánh giá & dự đoán VN30"**: Bổ sung cột "Giá hiện tại" (`format_price`), căn phải.
- **Bảng Top 10 "Chấm điểm và gợi ý 3 chiến lược"**: Thêm cột "Giá hiện tại" (`_fmt_strat_price`) cho cả 3 hồ sơ Ngắn/Trung/Dài hạn, lấy giá đóng cửa từ `market_service.list_stocks()`.
- **Lập lịch Worker 17:00**: Đăng ký job `daily_strategy_scoring` 17:00 Mon–Fri ICT trên APScheduler worker.
- **Hiển thị Dashboard**: Bổ sung bộ chọn 9 khung thời gian nến VNINDEX và làm rõ mối liên hệ giữa Điểm tổng hợp và Xếp hạng Grade A/B/C/D.
- Huấn luyện lại mô hình ML XGBoost từ CSDL (`train-model --source db`), lưu trữ artifact vào Model Registry.
- Thêm trang thứ 9 trên Dashboard Streamlit: **"Lịch sử Worker"** (3 tab: Lịch trình APScheduler 8 job, Nhật ký gửi email tự động, Hướng dẫn CLI vận hành).
- Cập nhật bộ test `tests/unit/test_dashboard_app.py` bao quát 9/9 trang, 10/10 test pass.

**Các task trước đó:** `T018` (Module gửi email tự động + Quản lý Email, 2026-09-28) · `T016` (Universe VN100/đa sàn + nến VNINDEX + Top 10 + login JWT, 2026-09-27) · `T015c` · `T015b` · `T015a` · `T016-LLM-local` (Ollama, 2026-09-26) · `D5` (chuẩn hóa tiếng Việt, 2026-09-26) · `D4` · `D3` · `D2` (dữ liệu thật, 2026-09-24/25) · `D1` · `T001` · `T003` + `T002` · `T004+T005` · `T006` + `T007` · `T008+T009+T010` · `T011` · `T013` · `T014` · `MAINT-2026-09-17`.
- Router `notifications` — 11 thao tác (`/recipients` CRUD, `/smtp`, `/schedule`, `/send-test`, `/preview-html`, `/logs`).
- Worker: 2 cron Mon–Fri (08:00 sáng, 15:30 chiều) → scheduler **5 job**.
- Dashboard trang **📧 Quản lý Email** (5 tab: gửi thử + preview, người nhận, SMTP Gmail, lịch gửi, logs).
- Validation: regex email stdlib (không thêm `email-validator`); cảnh báo khi password Gmail khác 16 ký tự (không phải App Password).

**Kiểm chứng (2026-09-29):** unit **589 thu thập (586 passed, 3 skipped)** · integration **31 passed** (fixture rollback ⇒ không chạm CSDL thật) · ruff + mypy (**140 tệp**) sạch · live: worker đăng ký `daily_eod_catchup` 15:50, lượt EOD nạp `prices 820` + `index_prices 12`, catch-up bỏ qua khi dữ liệu mới / cảnh báo khi mô phỏng phiên chưa đóng; preview email 16 KB, map lỗi 535 sang hướng dẫn App Password.

**Quy ước mới ghi nhận:** Lỗi SMTP từ Gmail khi ngắt kết nối sau lần AUTH hỏng lặp lại (`SMTPServerDisconnected`) → luôn hiển thị hướng dẫn App Password, không để lộ exception thô.

**Các task trước đó:** `T016` (Universe VN100/đa sàn + nến VNINDEX + Top 10 + login JWT, 2026-09-27; retrain 63.436 dòng `roc_auc=0.565`) · `T015c` · `T015b` · `T015a` · `T016-LLM-local` (Ollama, 2026-09-26) · `D5` (chuẩn hóa tiếng Việt, 2026-09-26) · `D4` · `D3` · `D2` (dữ liệu thật, 2026-09-24/25) · `D1` · `T001` · `T003` + `T002` · `T004+T005` · `T006` + `T007` · `T008+T009+T010` · `T011` · `T013` · `T014` · `MAINT-2026-09-17`.

## 4. Chặn / ghi nhận

- Nguồn dữ liệu **đã chọn** (T002) + **chuỗi thật đã kiểm chứng** (2026-09-25): Yahoo chart EOD + CaféF RSS gánh việc nạp (`VERIFIED_2026-09-25` trong `configs/sources.yaml`); SSIX/VNDirect/TCBS/DSC/WSJ vẫn chờ mạng/key → KI-006/KI-007 còn mở một phần.
- Đường đọc API trên TimescaleDB (`MARKET_DATA_SOURCE=db|auto` → KI-008 một phần); mặc định vẫn `memory`; API chưa có đường ghi; compose api/worker mặc định `auto` (cần rebuild image: `docker compose build api worker` + tạo lại container).
- Dịch vụ Docker đang chạy & khỏe mạnh (db, qdrant, api, worker, dashboard); migration + seed đã kiểm chứng với TimescaleDB đang chạy.
- Python cục bộ là 3.14; phụ thuộc CSDL (SQLAlchemy 2.0.52, Alembic 1.20, psycopg 3.3) cài & chạy được cục bộ. Image Docker dùng Python 3.12.
- `train-model` vẫn hard-code nguồn fixture → KI-012 chặn huấn luyện thật; lối mở là cờ `--source {memory,db}`.

---

## 5. Bước tiếp theo (theo thứ tự đặc tả §57)

```text
1.  THIẾT KẾ CSDL          → XONG (lược đồ + migration 0001 + seed, 2026-09-13)
2.  CẤU TRÚC REPO          → xong (khung)
3.  THIẾT KẾ NGUỒN DỮ LIỆU → XONG (2026-09-13)
4.  NẠP DỮ LIỆU            → XONG (T004) + chuỗi thật Yahoo/CaféF (2026-09-25)
5.  CHẤT LƯỢNG DỮ LIỆU     → XONG (T005)
6.  QUANT ENGINE           → XONG (T006/T007/T008 + job compute-scores trên dữ liệu thật)
7.  ENGINE BACKTEST        → XONG (T009; kiểm chứng thật còn giới hạn — KI-009)
8.  TẦNG API               → XONG (T010 + đường đọc CSDL W1)
9.  DASHBOARD              → XONG (T011 + nối dữ liệu thật + trang Tin tức & RAG)
10. RAG                    → XONG (T012 + 50 bài CaféF thật; Qdrant best-effort — KI-011 một phần)
11. TÁC TỬ AI              → XONG (T013)
12. DỰ ĐOÁN ML             → mã nguồn XONG (T014); huấn luyện thật chờ KI-012
12b. KIỂM TOÁN MÃ          → XONG (MAINT-2026-09-17: 16 sửa lỗi, 342 test)
12c. CỘT MỐC DỮ LIỆU THẬT  → XONG (2026-09-24/25; E2E 62/62 @94.88; 422 test)
12d. DỜI TÀI LIỆU          → XONG (2026-09-25: docs/htmldocs/ → docs/)
12e. DỊCH TÀI LIỆU         → XONG (2026-09-26: bản tiếng Việt docs/helper/memory-bank + sửa số liệu API)
13. TRÍ TUỆ DANH MỤC        → chưa làm
14. PRODUCTION             → T015
```

