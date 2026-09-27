# Tham chiếu tài nguyên (helper) — Bản tiếng Việt

## Nền tảng Nghiên cứu & Quyết định Đầu tư AI

> Thuật ngữ chuyên môn (tên bảng, biến môi trường, lệnh, đường dẫn) giữ nguyên tiếng Anh.

## Ngăn xếp công nghệ (§34)

| Tầng | Công nghệ | Phiên bản mục tiêu |
|---|---|---|
| Ngôn ngữ | Python | 3.12/3.13 (Docker); cục bộ 3.14 |
| Backend | FastAPI | 0.115+ |
| CSDL | PostgreSQL + TimescaleDB | timescale/timescaledb:latest-pg16 |
| Vector DB | Qdrant | qdrant/qdrant:latest |
| Dữ liệu | Pandas / Polars / NumPy | ghim trong pyproject |
| ML | scikit-learn, xgboost, lightgbm | Giai đoạn 6 |
| Tác tử | Orchestrator tất định (T013, không LLM); LangGraph dự kiến (§34) | Giai đoạn 5 |
| Dashboard | Streamlit | 1.3x |
| Migration | Alembic + SQLAlchemy | 2.x |

Image Docker của API/worker cài `.[dev,ml]`: scikit-learn `>=1.4,<2.0`,
xgboost `>=2.0,<3.0`, lightgbm `>=4.3,<5.0` (khai báo trong `pyproject.toml`).
Rebuild sau khi đổi phụ thuộc trong Dockerfile; `restart` không cập nhật gói.
Xem các bước xử lý sklearn trong `helper/deployment_vi.md`.

## Biến môi trường (từ `.env.example`)

| Biến | Mục đích |
|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | thông tin CSDL |
| `DATABASE_URL` | DSN SQLAlchemy |
| `QDRANT_URL` | endpoint Qdrant |
| `LLM_PROVIDER` / `LLM_API_KEY` / `LLM_MODEL` | trừu tượng hoá LLM (ADR-005) |
| `LLM_BASE_URL` / `LLM_TIMEOUT_SECONDS` / `LLM_THINK` | endpoint, hạn mức thời gian và bật/tắt khối suy luận của LLM local (T016); `local` = Ollama tại `http://host.docker.internal:11434`, model `qwen3.5`, `LLM_THINK=false` |
| `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` | dịch vụ embedding (Giai đoạn 4) |
| `LOG_LEVEL` | mức log |
| `MARKET_DATA_PROVIDER` / `MARKET_DATA_API_KEY` | chọn provider dữ liệu thị trường (T002) |
| `FUNDAMENTAL_DATA_PROVIDER` | chọn provider dữ liệu cơ bản (T002) |
| `NEWS_PROVIDER` / `NEWS_API_KEY` | chọn provider tin / key trả phí tuỳ chọn (T002) |
| `SSI_CONSUMER_ID` / `SSI_CONSUMER_SECRET` | Consumer ID & Secret của SSI FastConnect Data API v2 |
| `SSI_API_URL` | base URL SSI FastConnect (mặc định `https://fc-data.ssi.com.vn`) |
| `FINIPRO_ACCESS_TOKEN` | Bearer token SSI FiniPro/FastConnect có thể cấp trực tiếp (nếu có sẵn token) |
| `VIETSTOCK_API_KEY` | dữ liệu Vietstock VIP (tuỳ chọn, đang tắt) |
| `TRADINGECONOMICS_API_KEY` | tổng hợp vĩ mô (tuỳ chọn, đang tắt) |
| `MARKET_DATA_SOURCE` | đường đọc API: `memory` (mặc định, không CSDL) / `db` (TimescaleDB) / `auto` (dùng CSDL khi `prices` có dòng, ngược lại memory); compose mặc định `auto` |
| `SCHEDULER_JOBS_ENABLED` | `true` = chạy job news/EOD/scoring; `false` = tắt scheduler, `/news/ingest` vẫn dùng được |
| `API_AUTH_KEY` | (T015) khi đặt, mọi POST/PUT/PATCH/DELETE dưới `/api/v1/` (trừ `/auth/login`) và `GET /metrics` yêu cầu `Authorization: Bearer <key>`; để trống = tắt (demo/unit test) |
| `SCHEDULER_NEWS_SOURCE` / `SCHEDULER_NEWS_INTERVAL_MINUTES` | provider tin (mặc định `cafef`) + chu kỳ (mặc định `15` phút) |
| `SCHEDULER_EOD_SOURCE` / `SCHEDULER_EOD_CRON_HOUR` / `SCHEDULER_EOD_CRON_MINUTE` / `SCHEDULER_EOD_LOOKBACK_DAYS` | nguồn EOD **chính** (mặc định `ssix_finipro`; job tự chuyển `yahoo → vndirect → tcbs → dsc`) · Thứ 2–6 15:05 ICT (`15`/`5`) · cửa sổ nạp lại idempotent (`7` ngày) |
| `SCHEDULER_SCORING_CRON_HOUR` / `SCHEDULER_SCORING_CRON_MINUTE` | job chấm điểm Thứ 2–6 15:30 ICT (`15`/`30`), sau job EOD |
| `DATA_QUALITY_THRESHOLD` | cổng chất lượng 0–100 (`80.0`); lô dưới ngưỡng bị đánh dấu `below_threshold` và không dùng ở tầng dưới |

## Tích hợp bên thứ ba (T002 — xem `configs/sources.yaml`, thiết kế trong `docs/DATA_SOURCES_vi.md`)

| Tên (id) | Mục đích | Trạng thái |
|---|---|---|
| `ssix_finipro` (SSI FastConnect) | Chính: thị trường + cơ bản + sự kiện + tin | **Đã kiểm chứng 2026-09-27** (`Market/AccessToken` JWT + `Market/DailyOhlc` 68 dòng · quality 93.74 + `Market/DailyIndex` 34 dòng); dựng provider bằng `SSI_CONSUMER_ID`/`SSI_CONSUMER_SECRET` (hoặc `FINIPRO_ACCESS_TOKEN`) |
| `yahoo` | Dự phòng thị trường — EOD OHLCV cho mã `.VN` (anonymous) | **Đã kiểm chứng 2026-09-25**; quy tắc un-adjust tách + bỏ dòng placeholder trong `YahooChartProvider` |
| `vndirect`, `tcbs`, `dsc` | Dự phòng thị trường/cơ bản (anonymous, không chính thức) | Đã chọn làm dự phòng (vndirect/tcbs unreachable từ host 2026-09-25) |
| `sbv`, `gso`, `imf_worldbank` | Vĩ mô (công khai chính thức) | Đã chọn |
| `cafef`, `vnexpress`, `vietstock_news` | Tin tức Việt (RSS) | CaféF **đã kiểm chứng 2026-09-25** (`RssNewsProvider` parser stdlib; đã nạp 50 bài thật); còn lại đã chọn |
| `hose`, `hnx`, `vietstock`, `tradingeconomics`, `newsdata` | Bổ sung chính thức/cấp phép/trả phí | **Đang tắt** tới khi có quyết định cấp phép/chi phí |

> Mọi chứng thực đều được che; không bao giờ commit key thật. Cần egress whitelist cho API bên ngoài.

## Script CLI

- `python -m database.seeds.run_all` — nạp dữ liệu tham chiếu
- `python -m apps.worker.cli ingest --dataset prices --source fixture --symbols FPT,VCB --start … --end …` — chạy một collector
  (`--dataset prices` yêu cầu `--symbols`; thoát mã `2` thay vì báo một lần nạp rỗng là thành công)
- `python -m apps.worker.cli ingest --dataset prices --source ssix_finipro --symbols FPT,VCB,HPG,ACB --start 2026-09-01 --end 2026-09-26` — EOD qua **SSI FastConnect (nguồn chính)**, đã kiểm chứng 2026-09-27: fetched=68 written=68 quality=93.74 (cần `SSI_CONSUMER_ID`/`SSI_CONSUMER_SECRET`)
- `python -m apps.worker.cli ingest --dataset index_prices --source ssix_finipro --indexes VNINDEX,VN30 --start 2026-09-01 --end 2026-09-26` — chỉ số qua SSI (`Market/DailyIndex`, đã kiểm chứng: written=34)
- `python -m apps.worker.cli ingest --dataset prices --source yahoo --symbols FPT,VCB,HPG,ACB --start 2026-09-01 --end 2026-09-25` — EOD dự phòng qua Yahoo (đã kiểm chứng 2026-09-25: fetched=62 written=62 quality=94.88)
- `python -m apps.worker.cli compute-scores [--lookback 60]` — tính lại các hệ số từ giá vào `factor_scores`
- `python -m apps.worker.main scheduler` — chạy vòng APScheduler (news / EOD / scoring); `SCHEDULER_JOBS_ENABLED=false` để tắt job
- `python -m apps.worker.cli train-model [--horizon 5] [--source memory|db] [--algorithm xgboost|lightgbm]` — huấn luyện + hiệu chuẩn + đăng ký; **`--source db` ghi artifact vào bảng `model_registry`** (T015b) và in `"persisted": true`
  (`lightgbm` cần extra `[ml]` tuỳ chọn; CLI báo trung thực khi thiếu)
- `python -m apps.worker.cli ingest --dataset prices --source yahoo --symbols <30 mã VN30> --start 2024-09-27 --end 2026-09-27` — backfill 2 năm (đã kiểm chứng 2026-09-27: fetched=14810 written=14810 quality=91.87; upsert chia lô 1.000 dòng để tránh giới hạn 65.535 tham số của Postgres)
- `./scripts/backup_db.sh` — sao lưu `pg_dump` + gzip vào `backups/` (mặc định giữ 14 ngày; `BACKUP_DIR`/`RETENTION_DAYS` ghi đè)
- `./scripts/health_alert.sh` — kiểm tra `/healthz` + `/readyz` (dùng cho cron/cảnh báo; thoát mã ≠ 0 khi có sự cố)
- `python -m apps.worker.cli run-agent --task analyze --symbol FPT` — chạy tác tử ngoại tuyến
- `uvicorn apps.api.main:app --reload` — **chạy API REST phát triển** (cổng 8000)
- `python -m apps.api.main` — chạy API bằng `python -m`
- `curl localhost:8000/docs` — tài liệu tương tác (Swagger UI)
- `docker compose exec api alembic upgrade head` — migrate
- `docker compose exec api pytest` — chạy test trong container

## API (T010; 39 đường dẫn / 40 thao tác trên `/api/v1/*`, 2026-09-26)

- **Framework:** FastAPI 0.115 · endpoint `/api/v1/*`, tiền tố `docs/api.html`.
- **Router:** 12 tệp — nhóm market, stocks, fundamentals, technical, valuation, news, backtests, rag/evidence, agents/analysis, predictions, monitoring, auth.
- **Service:** protocol `MarketSource` (`apps/api/services/market_source.py`) — `MarketService` trong bộ nhớ, tất định (mặc định; KI-008 phần đọc đã mở) hoặc `DbMarketService` đọc TimescaleDB khi `MARKET_DATA_SOURCE=db|auto`; `/readyz` trả `market_source` dạng `<chế độ>-><service>`. Để mở rộng: nối repository SQLAlchemy mới vào `DbMarketService`, không đụng router.
- **Probe sẵn sàng:** `/healthz` (liveness tĩnh) và `/readyz` dò thật — `database` (`connected`/`connected-no-prices`/`unreachable`), `qdrant` (`up`/`offline-index-ready`), `agents` (`llm:<model>`/`offline:<tasks>`), `models` (`<model_id>@<version>` nạp từ `model_registry`, hoặc `stub`), `market_source`; probe luôn trả 200 (không 5xx). Prebuilt image đã cài extra `[qdrant]` (client Qdrant, không có torch) để mirror `dtck_docs` chạy thật.
- **Registry mô hình (T015b):** `train-model --source db` lưu pickled `ModelEntry` vào `model_registry.artifact`; API nạp lại qua `lifespan` (`src/ml/registry_store.py`) nên `/predictions` phục vụ model thật thay vì stub. Bảng có `target`/`horizon_days`; chu kỳ huấn luyện để NULL (không bịa theo §31).
- **Chiều ghi Backtest (T015b):** `POST /api/v1/backtests` chèn bản ghi vào `backtests` khi chạy DB mode (chi phí mặc định 15/5 bps); `GET /backtests*` phục vụ lại đúng bản ghi đó.
- **Schemas:** 21 lớp Pydantic trong `apps/api/schemas.py`, gồm `Page[T]` generic + `ErrorResponse`.
- **Kiểm thử:** `pytest tests/unit/test_api.py` (health/readyz, nhóm router, phân trang, 404) + `tests/unit/test_market_data_source.py` + integration `tests/integration/test_db_market.py`.
- **Kiểm chứng số liệu (2026-09-26):** con số lấy từ `app.openapi()` — 39 đường dẫn / 40 thao tác trên `/api/v1/*`; cộng `/healthz` + `/readyz` thành 41 đường dẫn / 42 thao tác. Các ghi chú cũ "38 đường dẫn / 39 thao tác" là đếm thiếu một đường dẫn.

## Quy trình cập nhật phụ thuộc

Khi `pyproject.toml`/`requirements*.txt` thay đổi → làm mới wheel trong `offline_package/` và cập nhật tệp này (quy tắc §2.4).

> Ghi chú: `PyYAML` đã được cài vào venv cục bộ để chạy (không bỏ qua) `tests/unit/test_sources_registry.py`
> (T002) nhưng **chưa** là phụ thuộc dự án — `pyproject.toml` không đổi. Nếu bạn đồng ý
> thêm `pyyaml` vào `[project.optional-dependencies] dev`, test registry cũng chạy được trong Docker/CI.
