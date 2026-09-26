# Bộ nhớ dự án — Hiện trạng (Bản tiếng Việt)

> Thuật ngữ chuyên môn (tên bảng, biến môi trường, lệnh, đường dẫn) giữ nguyên tiếng Anh.

**Cập nhật lần cuối:** 2026-09-26

---

## 1. Trạng thái theo đặc tả §58

```text
Đặc tả:         ████████████████████ 100%   (docs/SYSTEM_SPECIFICATION.md, v1.0)
Kiến trúc:      ████████████████████ 100%   (docs/ARCHITECTURE.md đã soạn)
CSDL:           ████████████████████ 100%   (lược đồ + migration Alembic 0001 + seed XONG)
Pipeline dữ liệu:████████████████████ 100%   (T004+T005 XONG + chuỗi thật [yahoo,vndirect,tcbs,dsc]; CaféF RSS đã kiểm chứng; E2E 62/62 @94.88)
Quant Engine:   ████████████████████ 100%   (T006+T007+T008 XONG + job compute-scores trên 4 mã thật)
Backtesting:    ██████████████████░░  90%   (T009 engine+chỉ số+walk-forward XONG; kiểm chứng thật giới hạn ~1 tháng lịch sử Yahoo — KI-009)
API:            ██████████████████░░  90%   (T010 xong; đường đọc TimescaleDB qua MARKET_DATA_SOURCE=db|auto — mặc định vẫn memory; đường ghi còn mở — KI-008)
Dashboard:      ███████████████████░  95%   (T011 + mở phong bì phân trang + trang Tin tức & RAG; dữ liệu thật khi API chạy chế độ db)
RAG:            ██████████████████░░  90%   (T012 + 50 bài CaféF thật đã nạp & kiểm chứng; Qdrant best-effort)
Tác tử AI:      ████████████████████  95%
ML:             ████████████████░░░░  80%   (T014: dataset + huấn luyện + hiệu chuẩn + registry + API /predictions XONG; huấn luyện thật chờ KI-012)
Production:     ███░░░░░░░░░░░░░░░░░  15%   (scheduler 3 job + compute-scores XONG 2026-09-25; JWT/RBAC/monitoring/alert/CI-CD → T015)
```

---

## 2. Hiện có gì (khung Phase-0 hoàn tất + thiết kế CSDL BƯỚC 2 đã triển khai)

- **Cấu trúc repo** đã dựng đầy đủ theo đặc tả §35 (`apps/`, `src/`, `database/`, `tests/`, `notebooks/`, `configs/`, `scripts/`, `docs/`, `memory-bank/`, `offline_package/`, `docker/`).
- **Bộ tài liệu** đầy đủ (13+ tệp, danh sách ở `project-context_vi.md` §7) — toàn bộ chuẩn hóa 100% tiếng Việt, đã loại bỏ các bản tiếng Anh trùng lặp (2026-09-26).
- **Memory bank** 100% bằng tiếng Việt và là nguồn chân lý duy nhất.
- `pyproject.toml`, `.env.example`, `.gitignore`, `README.md`, `docker-compose.yml`, Dockerfile — đã tạo.
- **Model SQLAlchemy** (`src/common/models/`) triển khai mọi bảng trong `docs/DATABASE_SCHEMA_vi.md` — 38 bảng, nguồn chân lý duy nhất (`Base.metadata`).
- **Migration Alembic** `database/migrations/versions/0001_initial_schema.py` → tạo toàn bộ bảng + chuyển 12 bảng chuỗi thời gian thành TimescaleDB hypertable (theo §17), có `upgrade`/`downgrade`. Đã kiểm chứng up → down → up với TimescaleDB Docker đang chạy.
- **Seed** (`database/seeds/`) — exchanges (HOSE/HNX/UPCOM), 10 sector + 15 industry, universe VN30 30 dòng. Idempotent; nối vào `database/seeds/run_all.py`.
- **Pipeline dữ liệu** (`src/data/`) — collectors, validators, normalizers, pipelines, providers (base + fixture + HTTP-JSON + registry), chấm điểm chất lượng (§39). FixtureProvider cho phép kiểm thử pipeline hoàn toàn ngoại tuyến. Worker CLI (`apps/worker/cli.py`) đã nối lệnh ingest.
- **Cột mốc dữ liệu thật (2026-09-24/25)** — `YahooChartProvider` (EOD VN công khai, priority 85, `VERIFIED_2026-09-25`; chuỗi `[yahoo,vndirect,tcbs,dsc]`; un-adjust tách qua `events=split`; giá đóng chưa điều chỉnh) + `RssNewsProvider` cho CaféF (`VERIFIED_2026-09-25`; 50 bài thật đã nạp, liên kết nhiều mã theo chunk). Nạp trực tiếp `ingest --source yahoo --symbols FPT,VCB,HPG,ACB` → **fetched=62 written=62 issues=0 quality=94.88** (đạt cổng); `compute-scores --lookback 60` → scored=4 mã thật vào `factor_scores`.
- **Đường đọc CSDL (W1, 2026-09-25)** — protocol `MarketSource` + `DbMarketService` (13 nhóm bảng thật, cache theo request) sau `MARKET_DATA_SOURCE=memory|db|auto` (`apps/api/dependencies.py`); router không đổi, `/readyz` báo `"source"`. Compose api/worker mặc định `auto`; code + `.env.example` mặc định `memory` để unit test không cần CSDL.
- **Scheduler worker (Option 2, 2026-09-24)** — APScheduler 3 job (`run_scheduler`): news mỗi N phút (CaféF), EOD Thứ 2–6 15:05 ICT (Yahoo), scoring Thứ 2–6 15:30 ICT (`compute-scores` trong tiến trình); fail-soft, `max_instances=1` + `coalesce`, `SCHEDULER_JOBS_ENABLED=false` để tắt. Tên `SCHEDULER_*` khớp giữa `Settings` ↔ `.env.example` ↔ `docker-compose.yml`.
- **Nối dữ liệu thật cho dashboard (Option 1, 2026-09-24)** — client mở phong bì phân trang `{items}`, thêm `search_rag`/`get_rag_status`/`get_evidence`; trang "Tin tức & RAG" mới; helper `evidence_rows`/`rag_doc_rows`.
- **Khung chất lượng dữ liệu** (`src/data/quality.py`) — chấm điểm 6 chiều (completeness, validity, consistency, uniqueness, freshness, accuracy) với trung bình có trọng số, chuẩn hoá lại và cổng ngưỡng (§39).
- **Scoring engine** (`src/quant/scoring/engine.py`, T008) — `decompose_score()` đóng góp theo hệ số với trọng số chuẩn hoá lại, `score_universe()` → danh sách `StockRanking` đã xếp hạng, `build_signal_label()` (POSITIVE/NEUTRAL/NEGATIVE), `build_confidence()`; payload giải thích cho mọi xếp hạng.
- **Engine backtesting** (`src/backtesting/`, T009) — `models.py`, `metrics.py` (total return, CAGR, volatility, Sharpe, Sortino, max drawdown, Calmar, win rate, profit factor, turnover, transaction-cost total), `engine.py` (`run_backtest`, `select_window`, logic rebalance/close-leg), `walkforward.py`. Tất định, tính chi phí, không look-ahead.
- **REST API** (`apps/api/`, T010; **39 đường dẫn / 40 thao tác** trên `/api/v1/*`, kiểm chứng 2026-09-26 bằng `app.openapi()`: 12 tệp router; không tính `/healthz`+`/readyz`; nhãn cũ "14 nhóm" đếm tag lỏng) — ứng dụng FastAPI với các nhóm router (`market`, `stocks`, `fundamentals`, `technical`, `valuation`, `news`, `backtests`, `rag`+`evidence`, `agents`+`analysis`, `auth`, `monitoring`, `predictions`) theo `docs/API_SPECIFICATION.md`; phân trang dùng chung + phong bì lỗi `not_found`; 21 schema Pydantic; `/healthz` + `/readyz` (báo `"source"` của dữ liệu thị trường); DI `MarketDep` chọn `MarketSource` (memory so với `DbMarketService`).
- **Dashboard Streamlit** (`apps/dashboard/`, T011) — `client.py` (`MarketClient`: HTTP-first qua `/api/v1/*`, mở phong bì phân trang `{items}`, phương thức RAG/bằng chứng, fallback `MarketService` trong tiến trình khi ngoại tuyến), `components.py` (biến đổi tín hiệu/định dạng/xếp hạng/phân rã thuần Python + `evidence_rows`/`rag_doc_rows`), `app.py` (7 trang: tổng quan thị trường, bộ lọc, xếp hạng, chi tiết mã, backtests, sức khỏe hệ thống, Tin tức & RAG; biểu đồ plotly nến/scatter/đóng góp).
- Kiểm thử: **422 passed, 3 skipped** (2026-09-25: `LLM_PROVIDER=mock pytest`); ruff + mypy (126 tệp) sạch. Lỗi tồn tại không liên quan: `test_smoke::test_api_config_loads` từ chối `.env` cục bộ có `LLM_PROVIDER=ollama`.
- **Hệ số cơ bản** (`src/market/fundamental/factors.py`) — tăng trưởng doanh thu/EPS, ROE, ROA, các biên lợi nhuận, D/E, khả năng trả lãi, FCF, biên FCF, chất lượng lợi nhuận. Tất cả trả `None` khi mẫu số bằng 0.
- **Định giá** (`src/market/valuation/valuation.py`) — P/E, forward P/E, P/B, EV/EBITDA, EV/Sales, tỉ suất cổ tức, PEG, enterprise value + hạng percentile (ngành/lịch sử).
- **Động lượng** (`src/market/momentum/momentum.py`) — lợi nhuận n ngày, đa khung, mở rộng khối lượng, động lượng tương đối so với benchmark.
- **Rủi ro** (`src/market/risk/risk.py`) — độ biến động niên hoá cuộn (log return), beta, max drawdown trượt, thanh khoản, rủi ro gap, nhóm rủi ro nợ.
- **Chấm điểm hệ số** (`src/quant/factors/scoring.py`) — trọng số nền §12 (fund 0.30/tech 0.20/mom 0.15/val 0.15/qual 0.10/risk 0.10), tổng hợp percentile-rank, điểm tổng chuẩn hoá lại, xếp hạng cổ phiếu.
- **Chỉ báo kỹ thuật** (`src/market/technical/indicators.py`) — SMA, EMA, RSI (làm trơn Wilder), MACD (12/26/9), Bollinger Bands (20, 2σ), ATR (14), OBV, volume SMA, sức mạnh tương đối so với benchmark. Thuần Python, tất định, kiểm chứng với giá trị tính tay (40 test).
- **RAG + engine bằng chứng** (`src/rag/` + `src/evidence/`, T012) — `HashEmbedding` (băm tất định, dim 128, model_name "hash-embed-v1"), `chunk_news_item` (chia cửa sổ trượt kèm metadata + mã + nguồn + published_at), `MemoryVectorStore` (cosine trong bộ nhớ; `upsert`/`query`) + `QdrantAdapter` tuỳ chọn (mirror best-effort khi import được `qdrant_client`), `Retriever` (hybrid: vector + trùng từ khoá + độ mới + tiên nghiệm độ tin cậy nguồn, lọc metadata symbol/doc_type/source), `rerank` (chấm lại kiểu RRF), singleton `RagService`, `src/evidence/engine.py` (`Evidence` §19 + `confidence_for` + `build_evidence` + `evidence_to_dict`). 3 endpoint API mới → tại T012 API có 26 đường dẫn / 27 thao tác; nay đã tăng lên **39 đường dẫn / 40 thao tác** (2026-09-26, kiểm chứng bằng `app.openapi()`). `readyz` báo trạng thái qdrant ("offline-index-ready" khi không có Qdrant). **2026-09-24/25:** 50 bài CaféF thật đã nạp vào chỉ mục (liên kết nhiều mã theo chunk); `/rag/search` + `/evidence` đã kiểm chứng trực tiếp.
- Repo Git trên nhánh `feat/data-source-design`.


---

## 3. Task vừa hoàn thành & Quy ước mới

**ID:** `D5 — Chuẩn hóa 100% tài liệu tiếng Việt, xóa bản tiếng Anh & ban hành quy ước tài liệu tiếng Việt (2026-09-26)`
**Trạng thái:** HOÀN THÀNH

**Quy ước bắt buộc:** Từ bây giờ khi cập nhật các file markdown của project chỉ sử dụng tiếng Việt và các file tiếng Việt. Toàn bộ 22 file tiếng Anh tương ứng và 2 file bản thảo trùng lặp đã được xóa bỏ hoàn toàn khỏi repository.

**Sản phẩm:**
- 12 tài liệu kỹ thuật trong `docs/*_vi.md` + 2 tài liệu nguyên bản tiếng Việt `SYSTEM_SPECIFICATION.md`, `AI_INVESTMENT_CONCEPT.md`.
- 2 tài liệu vận hành `helper/deployment_vi.md`, `helper/resources_vi.md`.
- 8 tệp memory-bank tiếng Việt `memory-bank/*_vi.md`.
- Toàn bộ README (`README.md`, `configs/README.md`, `database/migrations/README.md`, `notebooks/README.md`, `offline_package/README.md`, `scripts/README.md`) chuẩn hóa tiếng Việt.
- Sửa chuẩn xác số liệu API **39 đường dẫn / 40 thao tác** (kiểm chứng bằng `app.openapi()`).

**Task trước:** `D4 — Làm mới hướng dẫn triển khai cho bước 3 (2026-09-26)` — **HOÀN THÀNH**
**Sản phẩm D4:** `docs/DEPLOYMENT_vi.md` viết lại theo vị trí hiện tại (bước 3: rebuild → kiểm tra → nạp Yahoo + chấm điểm), bảng biến môi trường có `MARKET_DATA_SOURCE`/`SCHEDULER_*`/cảnh báo lệch DSN, roadmap cập nhật lại trạng thái; `helper/deployment_vi.md` cập nhật khớp theo.

**Kiểm chứng chung:** `LLM_PROVIDER=mock pytest` → 422 passed, 3 skipped · `ruff check .` sạch · `mypy` sạch (126 tệp) · 7 trang HTML cân bằng thẻ · kiểm tra liên kết nội bộ OK.

**Các task trước đó:** `D3 — Dời + làm mới tài liệu (2026-09-25)` · `D2 — Cột mốc dữ liệu thật W1–W3 + E2E (2026-09-24/25)` · `D1 — Trang tài liệu HTML tĩnh (2026-09-14)` · `T001` (2026-09-06) · `T003` + `T002` (2026-09-13) · `T004+T005` (2026-09-14) · `T006` + `T007` (2026-09-14) · `T008+T009+T010` (2026-09-15) · `T011` (2026-09-15) · `T013` (2026-09-15) · `T014` (2026-09-16) · `MAINT-2026-09-17`.

---

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

