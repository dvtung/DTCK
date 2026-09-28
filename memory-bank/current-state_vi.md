# Bộ nhớ dự án — Hiện trạng (Bản tiếng Việt)

> Thuật ngữ chuyên môn (tên bảng, biến môi trường, lệnh, đường dẫn) giữ nguyên tiếng Anh.

**Cập nhật lần cuối:** 2026-09-28

---

## 1. Trạng thái theo đặc tả §58

```text
Đặc tả:         ████████████████████ 100%   (docs/SYSTEM_SPECIFICATION.md, v1.0)
Kiến trúc:      ████████████████████ 100%   (docs/ARCHITECTURE.md đã soạn)
CSDL:           ████████████████████ 100%   (lược đồ 42 bảng + migration 0003_email_notifications + hypertable + seed XONG)
Pipeline dữ liệu:████████████████████ 100%   (T004+T005 XONG + chuỗi thật [ssix_finipro,yahoo,vndirect,tcbs,dsc]; CaféF RSS đã kiểm chứng; E2E 62/62 @94.88)
Quant Engine:   ████████████████████ 100%   (T006+T007+T008 XONG + job compute-scores trên 137 mã thật)
Backtesting:    ████████████████████ 100%   (T009 + chiều ghi CSDL + form Backtest trên dashboard)
API:            ████████████████████ 100%   (T010 + T016 + T018: 13 tệp router, 48 đường dẫn / 53 thao tác; đường đọc TimescaleDB qua MARKET_DATA_SOURCE=db|auto; `/readyz` dò thật, `market_source=auto->db`)
Dashboard:      ████████████████████ 100%   (T011 + T015c + T016 + T018: 8 trang gồm Tin tức & RAG, Quản lý Email, đăng nhập JWT; huy hiệu DỮ LIỆU THẬT; AppTest 8 trang)
RAG:            ████████████████████ 100%   (T012 + 50 bài CaféF thật + mirror collection dtck_docs, qdrant: up)
Tác tử AI:      ████████████████████ 100%   (T013 + T016 nối LLM local Ollama qwen3.5; agents: llm:qwen3.5)
ML:             ████████████████████ 100%   (T014 + T015b + T016: registry lưu CSDL + huấn luyện thật 63.436 dòng `roc_auc=0.565`; model price_direction_xgb@1.0.0)
Production:     ███████████████████░  95%   (scheduler 5 job + JWT/RBAC + /metrics + CI/CD + sao lưu/phục hồi + cảnh báo email tự động 08:00/15:30 → T015+T018)
Thông báo email:████████████████████ 100%   (T018: 4 bảng, router /notifications 11 thao tác, 2 cron Mon–Fri 08:00/15:30 + kiểm thử end-to-end)
```

---

## 2. Hiện có gì (khung Phase-0 hoàn tất + thiết kế CSDL BƯỚC 2 đã triển khai)

- **Cấu trúc repo** đã dựng đầy đủ theo đặc tả §35 (`apps/`, `src/`, `database/`, `tests/`, `notebooks/`, `configs/`, `scripts/`, `docs/`, `memory-bank/`, `offline_package/`, `docker/`).
- **Bộ tài liệu** đầy đủ (13+ tệp, danh sách ở `project-context_vi.md` §7) — toàn bộ chuẩn hóa 100% tiếng Việt, đã loại bỏ các bản tiếng Anh trùng lặp (2026-09-26).
- **Memory bank** 100% bằng tiếng Việt và là nguồn chân lý duy nhất.
- `pyproject.toml`, `.env.example`, `.gitignore`, `README.md`, `docker-compose.yml`, Dockerfile — đã tạo.
- **Model SQLAlchemy** (`src/common/models/`) triển khai mọi bảng trong `docs/DATABASE_SCHEMA_vi.md` — 42 bảng (gồm 4 bảng `notifications` của T018), nguồn chân lý duy nhất (`Base.metadata`).
- **Migration Alembic** `database/migrations/versions/` → head `0003_email_notifications`; 12 bảng chuỗi thời gian là TimescaleDB hypertable (theo §17), có `upgrade`/`downgrade`. Đã kiểm chứng up → down → up với TimescaleDB Docker đang chạy.
- **Seed** (`database/seeds/`) — exchanges (HOSE/HNX/UPCOM), 10 sector + 15 industry, universe mở rộng T016 (VN30 + VN100 + HNX/UPCOM, 138 mã). Idempotent; nối vào `database/seeds/run_all.py`.
- **Pipeline dữ liệu** (`src/data/`) — collectors, validators, normalizers, pipelines, providers (base + fixture + HTTP-JSON + registry), chấm điểm chất lượng (§39). FixtureProvider cho phép kiểm thử pipeline hoàn toàn ngoại tuyến. Worker CLI (`apps/worker/cli.py`) đã nối lệnh ingest.
- **Cột mốc dữ liệu thật (2026-09-24/25/27)** — **`SSIFastConnectProvider` là nguồn thị trường CHÍNH** (`priority 100`, `VERIFIED_2026-09-27`: `Market/AccessToken` đổi JWT, `Market/DailyOhlc` 68 dòng cho FPT,VCB,HPG,ACB · quality 93.74, `Market/DailyIndex` 34 dòng cho VNINDEX,VN30; chuỗi chạy tự động `ssix_finipro → yahoo → vndirect → tcbs → dsc` qua `market_provider_chain` + job EOD) + `YahooChartProvider` dự phòng (EOD VN, priority 85, `VERIFIED_2026-09-25`; un-adjust tách qua `events=split`; giá đóng chưa điều chỉnh) + `RssNewsProvider` cho CaféF (`VERIFIED_2026-09-25`; 50 bài thật đã nạp). CSDL hiện có 716 dòng `prices` (source `ssix_finipro`) + 34 dòng `index_prices`.
- **Đường đọc CSDL (W1, 2026-09-25)** — protocol `MarketSource` + `DbMarketService` (13 nhóm bảng thật, cache theo request) sau `MARKET_DATA_SOURCE=memory|db|auto` (`apps/api/dependencies.py`); router không đổi, `/readyz` trả `market_source` (`<chế độ>-><service>`). Compose api/worker mặc định `auto`; code + `.env.example` mặc định `memory` để unit test không cần CSDL.
- **`/readyz` trung thực (2026-09-27)** — `apps/api/main.py` dò thật từng phụ thuộc (không hardcode): `database` (`connected`/`connected-no-prices`/`unreachable`, dùng `database_is_ready`), `qdrant` (`up`/`offline-index-ready`), `agents` (`llm:<model>` | `offline:<tasks>`) + khoá `market_source`; probe không bao giờ ném 5xx. Image api/worker cài extra `[qdrant]` nên collection `dtck_docs` được mirror thật (`qdrant: up`).
- **Scheduler worker (Option 2, 2026-09-24; cập nhật 2026-09-28)** — APScheduler **5 job** (`run_scheduler`): news mỗi N phút (CaféF), EOD Thứ 2–6 15:05 ICT (`SCHEDULER_EOD_SOURCE=ssix_finipro` → dự phòng `yahoo → vndirect → tcbs → dsc`; nguồn lỗi/0 dòng ⇒ tự chuyển), scoring Thứ 2–6 15:30 ICT (`compute-scores` trong tiến trình), **báo cáo email Thứ 2–6 08:00 + 15:30 ICT** (T018, gửi bản tin HTML Tổng quan qua Gmail SMTP, ghi `email_send_logs`); fail-soft, `max_instances=1` + `coalesce`, `SCHEDULER_JOBS_ENABLED=false` để tắt. Tên `SCHEDULER_*` khớp giữa `Settings` ↔ `.env.example` ↔ `docker-compose.yml`.
- **Nối dữ liệu thật cho dashboard (Option 1, 2026-09-24)** — client mở phong bì phân trang `{items}`, thêm `search_rag`/`get_rag_status`/`get_evidence`; trang "Tin tức & RAG" mới; helper `evidence_rows`/`rag_doc_rows`.
- **Khung chất lượng dữ liệu** (`src/data/quality.py`) — chấm điểm 6 chiều (completeness, validity, consistency, uniqueness, freshness, accuracy) với trung bình có trọng số, chuẩn hoá lại và cổng ngưỡng (§39).
- **Scoring engine** (`src/quant/scoring/engine.py`, T008) — `decompose_score()` đóng góp theo hệ số với trọng số chuẩn hoá lại, `score_universe()` → danh sách `StockRanking` đã xếp hạng, `build_signal_label()` (POSITIVE/NEUTRAL/NEGATIVE), `build_confidence()`; payload giải thích cho mọi xếp hạng.
- **Engine backtesting** (`src/backtesting/`, T009) — `models.py`, `metrics.py` (total return, CAGR, volatility, Sharpe, Sortino, max drawdown, Calmar, win rate, profit factor, turnover, transaction-cost total), `engine.py` (`run_backtest`, `select_window`, logic rebalance/close-leg), `walkforward.py`. Tất định, tính chi phí, không look-ahead.
- **REST API** (`apps/api/`, T010 + T016 + T018; **48 đường dẫn / 53 thao tác** trên `/api/v1/*`, kiểm chứng 2026-09-28 bằng `app.openapi()`: **13 tệp router** gồm `notifications`; không tính `/healthz`+`/readyz`+`/metrics`) — FastAPI với các nhóm router theo `docs/API_SPECIFICATION.md` (phân trang dùng chung + phong bì lỗi `not_found`; 24 schema Pydantic; `/healthz` + `/readyz` với `market_source=auto->db`; DI `MarketDep` chọn `MarketSource`).
- **Dashboard Streamlit** (`apps/dashboard/`, T011 + T015c + T016 + T018) — `client.py` (HTTP-first, mở phong bì phân trang, RAG/bằng chứng + **email notifications** + **đăng nhập JWT**), `app.py` (**8 trang**: tổng quan + nến VNINDEX + Top 10 tăng/giảm, bộ lọc 3 sàn, xếp hạng 30 mã, chi tiết mã, backtests, Tin tức & RAG, **Quản lý Email**, sức khỏe; AppTest 8 trang).
- Kiểm thử **(2026-09-28):** riêng `tests/unit` = **523 passed, 3 skipped** (thêm T016 `?vn100=`/index-prices/movers/sidebar-login, T018 9+4 bài email/scheduler/API) và `tests/integration` = **28 passed** (thêm email persistence/dispatch mock); ruff + mypy (**138 tệp**) sạch. Các cột mốc trước: 499 (T015c) · 510 (T016 + 2 bài AppTest) · 521 (T018 mailer/service/API).
- **Hệ số cơ bản** (`src/market/fundamental/factors.py`) — tăng trưởng doanh thu/EPS, ROE, ROA, biên lợi nhuận, D/E, FCF (tỉ lệ 0–100); trả `None` khi mẫu số bằng 0 (không bịa số).
- **Định giá** (`src/market/valuation/valuation.py`) — P/E, forward P/E, P/B, EV/EBITDA, EV/Sales, tỉ suất cổ tức, PEG, enterprise value + hạng percentile (ngành/lịch sử).
- **Động lượng** (`src/market/momentum/momentum.py`) — lợi nhuận n ngày, đa khung, mở rộng khối lượng, động lượng tương đối so với benchmark.
- **Rủi ro** (`src/market/risk/risk.py`) — độ biến động niên hoá cuộn (log return), beta, max drawdown trượt, thanh khoản, rủi ro gap, nhóm rủi ro nợ.
- **Chấm điểm hệ số** (`src/quant/factors/scoring.py`) — trọng số nền §12 (fund 0.30/tech 0.20/mom 0.15/val 0.15/qual 0.10/risk 0.10), tổng hợp percentile-rank, điểm tổng chuẩn hoá lại, xếp hạng cổ phiếu.
- **Chỉ báo kỹ thuật** (`src/market/technical/indicators.py`) — SMA, EMA, RSI (làm trơn Wilder), MACD (12/26/9), Bollinger Bands (20, 2σ), ATR (14), OBV, volume SMA, sức mạnh tương đối so với benchmark. Thuần Python, tất định, kiểm chứng với giá trị tính tay (40 test).
- **RAG + engine bằng chứng** (`src/rag/` + `src/evidence/`, T012) — `HashEmbedding` (băm tất định, dim 128, model_name "hash-embed-v1"), `chunk_news_item` (chia cửa sổ trượt kèm metadata + mã + nguồn + published_at), `MemoryVectorStore` (cosine trong bộ nhớ; `upsert`/`query`) + `QdrantAdapter` tuỳ chọn (mirror best-effort khi import được `qdrant_client`), `Retriever` (hybrid: vector + trùng từ khoá + độ mới + tiên nghiệm độ tin cậy nguồn, lọc metadata symbol/doc_type/source), `rerank` (chấm lại kiểu RRF), singleton `RagService`, `src/evidence/engine.py` (`Evidence` §19 + `confidence_for` + `build_evidence` + `evidence_to_dict`). 3 endpoint API mới → tại T012 API có 26 đường dẫn / 27 thao tác; nay đã tăng lên **48 đường dẫn / 53 thao tác** (2026-09-28, kiểm chứng bằng `app.openapi()`). `readyz` báo trạng thái qdrant ("offline-index-ready" khi không có Qdrant). **2026-09-24/25:** 50 bài CaféF thật đã nạp vào chỉ mục (liên kết nhiều mã theo chunk); `/rag/search` + `/evidence` đã kiểm chứng trực tiếp.
- **Tác tử AI + tầng suy luận LLM** (`src/agents/`, T013 + T016, 2026-09-26) — 4 tác tử (Research/Analysis/Monitoring/Portfolio) + `Orchestrator` (retry/timeout §45, audit §31, registry §41) + `ToolCatalog`; lõi tất định ngoại tuyến. T016 thêm `src/agents/llm/client.py` (ADR-005: `LLMClient` Protocol, `MockLLMClient`, `OllamaLLMClient` gọi Ollama `/api/generate` với `think=false`, `create_llm_client`): `LLM_PROVIDER=mock` ⇒ không tạo client (baseline tất định), `local` ⇒ Analysis Agent sinh `thesis` tiếng Việt từ dữ liệu tool (điểm/bằng chứng/catalysts/risks/confidence không đổi, lỗi ⟶ rơi về mẫu), nhãn audit `deterministic-quant-v1+<model>`, `GET /api/v1/agents` báo `llm_model`/`reasoning`. Cấu hình: `LLM_PROVIDER`/`LLM_MODEL`/`LLM_BASE_URL`/`LLM_TIMEOUT_SECONDS`/`LLM_THINK`.
- Repo Git trên nhánh `vndocver`.


---

## 3. Task vừa hoàn thành & Quy ước mới

**ID:** `T018 — Module gửi email tự động (Gmail SMTP) + Trang quản trị dashboard (2026-09-28)`
**Trạng thái:** HOÀN THÀNH

**Sản phẩm:**
- `src/notifications/` — `report_generator.py` (HTML bản tin Tổng quan), `smtp_mailer.py` (stdlib, STARTTLS/SSL, map lỗi AUTH/disconnect/recipient sang tiếng Việt), `service.py` (recipients, SMTP, schedule, logs, dispatch).
- `src/common/models/notifications.py` — 4 bảng (42 bảng tổng); migration `0003_email_notifications` (head).
- Router `notifications` — 11 thao tác (`/recipients` CRUD, `/smtp`, `/schedule`, `/send-test`, `/preview-html`, `/logs`).
- Worker: 2 cron Mon–Fri (08:00 sáng, 15:30 chiều) → scheduler **5 job**.
- Dashboard trang **📧 Quản lý Email** (5 tab: gửi thử + preview, người nhận, SMTP Gmail, lịch gửi, logs).
- Validation: regex email stdlib (không thêm `email-validator`); cảnh báo khi password Gmail khác 16 ký tự (không phải App Password).

**Kiểm chứng:** unit **523 passed** · integration **28 passed** · ruff + mypy (**138 tệp**) sạch · live: preview 16 KB, trace SMTP đến AUTH, map lỗi 535 sang hướng dẫn App Password.

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

