# Bộ nhớ dự án — Task đang làm (Bản tiếng Việt)

> Thuật ngữ chuyên môn (tên bảng, biến môi trường, lệnh, đường dẫn) giữ nguyên tiếng Anh.

## Task: Chuẩn hóa 100% tài liệu tiếng Việt — Xóa bỏ các bản tiếng Anh & Ban hành quy ước tài liệu tiếng Việt

**Trạng thái:** HOÀN THÀNH (2026-09-26)
**Quy ước bắt buộc mới:** Từ bây giờ khi cập nhật các file markdown của project chỉ sử dụng tiếng Việt và các file tiếng Việt. Toàn bộ các file tiếng Anh tương ứng đã bị xóa bỏ để đảm bảo tính duy nhất và nhất quán của tài liệu.

### Các công việc đã thực hiện:
- [x] **Rà soát toàn bộ tệp markdown**: Kiểm tra và xác nhận mọi tài liệu trong `docs/`, `helper/`, `memory-bank/`, `configs/`, `database/migrations/`, `notebooks/`, `offline_package/`, `scripts/` và `README.md` đều có đầy đủ nội dung bằng tiếng Việt.
- [x] **Xóa bỏ các file trùng lặp / thừa**:
  - Xóa 2 bản thảo trùng lặp ở thư mục gốc: `AI powered Investment.md` và `SYSTEM_SPECIFICATION.md v1.0.md` (nội dung chuẩn đã có trong `docs/AI_INVESTMENT_CONCEPT.md` và `docs/SYSTEM_SPECIFICATION.md`).
  - Xóa toàn bộ 22 file tiếng Anh đã có bản tiếng Việt tương ứng:
    - `docs/` (12 file): `AGENT_ARCHITECTURE.md`, `API_SPECIFICATION.md`, `ARCHITECTURE.md`, `BACKTESTING.md`, `DATABASE_SCHEMA.md`, `DATA_ARCHITECTURE.md`, `DATA_SOURCES.md`, `DEPLOYMENT.md`, `ML_ARCHITECTURE.md`, `QUANT_ENGINE.md`, `RAG_ARCHITECTURE.md`, `SECURITY.md`.
    - `helper/` (2 file): `deployment.md`, `resources.md`.
    - `memory-bank/` (8 file): `active-task.md`, `architecture-decisions.md`, `changelog.md`, `current-state.md`, `decisions.md`, `known-issues.md`, `project-context.md`, `tasks.md`.
- [x] **Việt hóa các README phụ trợ**:
  - `README.md` gốc repo được viết lại 100% bằng tiếng Việt.
  - `configs/README.md`, `database/migrations/README.md`, `notebooks/README.md`, `offline_package/README.md`, `scripts/README.md` đã được dịch sang tiếng Việt hoàn chỉnh.
- [x] **Làm sạch các thông báo nguồn trôi lệch**:
  - Gỡ bỏ hoàn toàn các câu chú thích `> Bản gốc tiếng Anh: ...` và `> Bản tiếng Anh là nguồn chính thức` khỏi header của các file `*_vi.md` trong `docs/`, `helper/`, `memory-bank/`.
  - Cập nhật tài liệu tham chiếu trong `docs/status.html`, `helper/deployment_vi.md`, `memory-bank/project-context_vi.md`, `current-state_vi.md`, `tasks_vi.md` và `changelog_vi.md`.
- [x] **Ghi nhớ vào Memory Bank**:
  - Ban hành và ghi nhận quy tắc cốt lõi: Tài liệu dự án từ nay vận hành 100% bằng tiếng Việt trên các file tiếng Việt.
- [x] **Kiểm chứng hệ thống**:
  - Chạy `pytest`, `ruff check .`, `mypy` để đảm bảo không có bất kỳ regression hoặc đứt gãy nào.

---

## Task trước: Lộ trình triển khai tuần tự — Nối dữ liệu thật cho Dashboard & trang RAG (Option 1), Scheduler worker nền (Option 2), Provider EOD công khai cho thị trường Việt Nam (Option 3)


**Trạng thái:** ĐANG TRIỂN KHAI
**Bước hiện tại:** Option 3 (Provider EOD công khai) — triển khai + kiểm chứng xong

### Kế hoạch thực hiện:

- [x] **Bước 1: Nối dữ liệu thật cho Dashboard & trang RAG (Option 1)**
  - [x] Phân tích fallback và phong bì phân trang của DashboardClient.
  - [x] Cập nhật `apps/dashboard/client.py`:
    - Cho `list_stocks()`, `get_news()`, `get_backtests()` mở phong bì phân trang `{"items": [...]}` do FastAPI trả về (`/api/v1/stocks`, `/api/v1/news`, `/api/v1/backtests`) mà vẫn giữ tương thích list cho fallback ngoại tuyến.
    - Thêm phương thức cho tìm kiếm RAG (`search_rag(query, symbol=None, top_k=5)`), trạng thái RAG (`get_rag_status()`) và liệt kê bằng chứng (`get_evidence(query, symbol=None, top_k=5)`).
  - [x] Cập nhật `apps/dashboard/components.py`:
    - Thêm helper trình bày cho bằng chứng và mục RAG (ví dụ `evidence_rows()`, định dạng điểm, nhãn tin cậy).
  - [x] Cập nhật `apps/dashboard/app.py`:
    - Thêm trang "📰 Tin tức & RAG" (xem tin mới nạp, lọc theo mã/nguồn, tìm kiếm ngữ nghĩa tương tác kèm trích dẫn/đoạn bằng chứng).
  - [x] Cập nhật `tests/unit/test_dashboard.py` với unit test đầy đủ cho việc mở phong bì phân trang, gọi client RAG và helper trình bày.

- [x] **Bước 2: Job nền APScheduler cho worker (Option 2)**
  - [x] Cấu hình job định kỳ trong `apps/worker/main.py`:
    - Nạp tin tức định kỳ (mỗi 15–30 phút qua provider `cafef` / dự phòng).
    - Job chấm điểm hệ số EOD hằng ngày sau giờ đóng cửa (ví dụ 15:30 giờ VN các ngày trong tuần).
  - [x] Thêm test cho cấu hình job của scheduler.

- [x] **Bước 3: Provider dữ liệu EOD công khai cho thị trường Việt Nam (Option 3)**
  - [x] Triển khai provider EOD công khai tuân theo `DataProvider`
        (`src/data/providers/yahoo_chart.py` — `YahooChartProvider`, lớp con của
        `HttpJsonProvider`; chỉ override `_build_request` + `_map_rows`).
  - [x] Nối vào `configs/sources.yaml` (`yahoo`, priority 85,
        `endpoints_status: VERIFIED_2026-09-25`) và `create_provider`
        (dispatch `endpoints.eod.client: yahoo_chart`); chuỗi dự phòng thị trường
        nay là `[yahoo, vndirect, tcbs, dsc]`.
  - [x] Job `daily_eod_ingestion` cho worker (Thứ 2–6 15:05 ICT, trước scoring
        15:30) + các setting (`scheduler_eod_source/cron_hour/cron_minute/lookback_days`).
  - [x] Unit test: `tests/unit/test_yahoo_chart_provider.py` (13 test,
        fixture đã ghi `tests/fixtures/yahoo_chart_sample.json` gồm sự kiện tách
        FPT 11:10 ngày 2026-09-21), test scheduler mở rộng lên 7.

### Option 3 — Kiểm chứng (2026-09-25):

- `LLM_PROVIDER=mock pytest` → **422 passed, 3 skipped**; `ruff check .` sạch; `mypy` sạch (126 tệp).
- Trực tiếp: `DTCK_LIVE_TESTS=1 pytest -m live` → **2 passed** (Yahoo + CaféF).
- Nạp end-to-end (worker CLI, TimescaleDB dev): `ingest --dataset prices
  --source yahoo --symbols FPT,VCB,HPG,ACB --start 2026-09-01 --end 2026-09-25`
  → **fetched=62 written=62 skipped=0 issues=0 quality=94.88** (đạt cổng);
  đã xác nhận in giá thô chưa điều chỉnh trong `prices` (FPT 2026-09-03 close 72200,
  source=yahoo); FPT có 14 dòng so với 16 của các mã khác (các ngày placeholder
  volume 0 vắng mặt một cách trung thực). `compute-scores --lookback 60` → scored=4 mã thật.
- Lưu ý đã biết (ghi trong `configs/sources.yaml` + `docs/DATA_SOURCES.md` §8):
  `trading_value` = xấp xỉ close × volume (Yahoo không có trường turnover);
  un-adjust tách qua `events=split`; `meta.fullExchangeName` không dùng được
  (nhãn `exchange` trong config chỉ mang tính gắn nhãn — `prices` khoá theo `stock_id`).
- Lỗi tồn tại từ trước, không liên quan task này: `test_smoke.py::test_api_config_loads`
  từ chối `LLM_PROVIDER=ollama` trong `.env` cục bộ (chạy bộ test với `LLM_PROVIDER=mock`).


## Workstream W1, W1b, W2: đường đọc CSDL, chấm điểm hệ số quant, nạp tin CaféF RSS (2026-09-25)

**Trạng thái:** HOÀN THÀNH
**Mục tiêu:** Nối đường đọc FastAPI vào TimescaleDB (W1), triển khai job chấm điểm hệ số quant hằng ngày (W1b), và nối nạp tin trực tiếp từ CaféF RSS không cần chứng thực bên ngoài (W2).

### Sản phẩm & kiểm chứng:

- [x] **W1 (đường đọc CSDL)**:
  - Tạo protocol `apps/api/services/market_source.py` + `DbMarketService` trong `apps/api/services/db_market.py`.
  - Thêm `ranking_payload.py` để tách việc chuyển đổi lược đồ xếp hạng khỏi nguồn trong bộ nhớ so với CSDL.
  - Cấu hình `MARKET_DATA_SOURCE=memory|db|auto` trong `apps/api/dependencies.py` và `apps/api/config.py`.
  - Cập nhật router (`fundamentals`, `valuation`, `technical`, `news`) để dùng `MarketSource`.
  - Unit test: `tests/unit/test_market_data_source.py`.
  - Integration test: `tests/integration/test_db_market.py` chạy với PostgreSQL/TimescaleDB thật.
- [x] **W1b (job chấm điểm)**:
  - Tạo `src/quant/scoring/job.py` tính các hệ số thô từ giá (RSI-14, động lượng 63 ngày, đảo dấu độ biến động 20 ngày) và upsert vào `factor_scores` với giá trị `NULL` trung thực cho các chiều chưa có dữ liệu.
  - Thêm lệnh `compute-scores` vào `apps/worker/cli.py`.
  - Unit test: `tests/unit/test_scoring_job.py`.
  - Integration test: `tests/integration/test_scoring_job.py`.
- [x] **W2 (provider CaféF RSS & liên kết mã cho tin)**:
  - Ghi fixture XML thật (`tests/fixtures/cafef_rss_sample.xml`).
  - Triển khai parser RSS/Atom bằng thư viện chuẩn và `RssNewsProvider` trong `src/data/providers/rss.py`.
  - Đăng ký provider `cafef` trong `configs/sources.yaml` (`VERIFIED_2026-09-25`) và `src/data/providers/registry.py`.
  - Hỗ trợ trích nhiều mã và lọc theo mã trong `src/rag/ingestion/chunking.py` và `src/rag/retrieval/store.py`.
  - Nối khớp mã vào phần nạp tin của worker (`apps/worker/cli.py`).
  - Unit test: `tests/unit/test_rss_provider.py` (MockTransport + parse fixture XML + xử lý ngày tháng).
  - Kiểm chứng trực tiếp: nạp 50 bài thật từ CaféF; xác nhận lưu trong `news` và liên kết trong `news_symbols`; kiểm chứng `/api/v1/news`, `/api/v1/rag/search` và `/api/v1/evidence`.
- [x] **Cổng chất lượng**:
  - `ruff check .` -> All checks passed!
  - `mypy` -> Success: no issues found in 125 source files.
  - `pytest` -> 399 passed, 2 skipped trong ~3.0s.

## Task trước đó

**Trạng thái:** HOÀN THÀNH
**Mục tiêu:** API khởi động với phụ thuộc ML tái lập được trong Docker; giữ các import ML công khai.
**Phạm vi:** Dockerfile API/worker, export ML lazy, test hồi quy và tài liệu triển khai.
**Ràng buộc:** Giữ nguyên các sửa đổi Compose sẵn có và volume CSDL; dùng extra `[ml]` sẵn có.

- [x] Build image API/worker: `BUILD_EXIT_CODE=0`.
- [x] Chỉ tạo lại API/worker bằng `docker compose up -d --no-deps api worker`.
- [x] API import được sklearn 1.9.1, xgboost 2.1.4, lightgbm 4.7.0; worker import được `ModelTrainer`.
- [x] `/healthz` và `/api/v1/predictions/VNM` trong container trả HTTP 200.
- [x] Lint, kiểu và test hồi quy (bao gồm import ML tuỳ chọn bị chặn).
  - `ruff check .` sạch · `mypy src apps` sạch (119 tệp) · `pytest tests/unit` **343 passed, 1 skipped**
    (chạy với `LLM_PROVIDER=mock`; `.env` cục bộ đặt `ollama` và bị allowlist của smoke test từ chối)
  - Trong container: `import sklearn` → 1.9.1; smoke test import-bị-chặn chứng minh `apps.api.main`
    import được mà không cần sklearn và `src.ml.training` vẫn lazy.

---

**ID:** `T014 — ML prediction: feature dataset + training + calibration + registry + predictions API (Phase 6)`
**Trạng thái:** HOÀN THÀNH phần mã nguồn (2026-09-16); huấn luyện trên dữ liệu thật chờ KI-012

**Mục tiêu:** Dự đoán huấn luyện cổ điển theo đặc tả §14/§15/§26/§40 + `docs/ML_ARCHITECTURE.md`: dataset đặc trưng as-of (không rò rỉ), huấn luyện XGBoost với chia theo thời gian, hiệu chuẩn kiểu Platt, registry model có vòng đời phiên bản, endpoint `/api/v1/predictions`, CLI `train-model` cho worker.

**Phạm vi:** `src/ml/` (feature_dataset, training, model_registry, predictor, schemas), `apps/api/routers/predictions.py`, `apps/worker/cli.py` (train-model), `tests/unit/test_ml_*.py`, `test_t014_t015.py`.

**Ràng buộc:** Tất định, ưu tiên ngoại tuyến; tương thích sklearn 1.8+ (không dùng `CalibratedClassifierCV cv="prefit"`); không rò rỉ mục tiêu trong đặc trưng.

**Sửa lỗi chính trong lúc triển khai:**

- **Loại bỏ rò rỉ mục tiêu:** cột lợi nhuận tương lai `horizon_return_*` từng nằm trong ma trận đặc trưng (`horizon_return_5d` == mục tiêu đúng nghĩa); đã xoá khỏi đặc trưng, chỉ giữ trong mục tiêu. Test hồi quy chứng minh đặc trưng bất biến với cú sốc giá tương lai.
- **Lỗi chia theo ngày trùng:** chia theo thời gian từng dùng số dòng; một ngày có thể rơi vào hai phần. Nay chia theo ngày giao dịch duy nhất; có chốt chặn từ chối phần chỉ có một lớp, khung lệch và nhãn không phải 0/1.
- **Đặc trưng mã bằng `hash()`** bị ngẫu nhiên hoá theo tiến trình (PYTHONHASHSEED) → thay bằng `zlib.crc32`.
- **KI-012 (mới):** fixture thị trường tổng hợp tăng đơn điệu → 100% nhãn 5 ngày dương; không thể fit classifier thật. `train()`/`train-model` báo lỗi to thay vì phát ra model giả; predictor phục vụ stub dự phòng tất định. Huấn luyện thật chờ nối CSDL (KI-006/007/008).
  - *Cập nhật 2026-09-25:* đường đọc CSDL đã có (`DbMarketService`); lối mở là thêm cờ `--source db` cho `train-model` (xem `tasks_vi.md`).

**Nghiệm thu:**

- [x] `ruff check .` sạch
- [x] `mypy` sạch — "Success: no issues found in 119 source files"
- [x] `pytest -q` — **325 passed** (+12 test ML/API; rò rỉ + hợp đồng huấn luyện)
- [x] `docs/status.html` đã cập nhật (ML 80%, KI-012, roadmap → T015)
- [x] memory bank đã cập nhật (active-task/current-state/changelog/tasks)

