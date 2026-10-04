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
| `SCHEDULER_JOBS_ENABLED` | `true` = chạy job news/EOD/catch-up/scoring; `false` = tắt scheduler, `/news/ingest` vẫn dùng được |
| `API_AUTH_KEY` | (T015) khi đặt, mọi POST/PUT/PATCH/DELETE dưới `/api/v1/` (trừ `/auth/login`) và `GET /metrics` yêu cầu `Authorization: Bearer <key>`; để trống = tắt (demo/unit test) |
| `AUTH_JWT_SECRET` / `AUTH_JWT_TTL_SECONDS` / `AUTH_REFRESH_TTL_SECONDS` | (T015b) bí mật HS256 + TTL cho JWT cấp tại `POST /api/v1/auth/login`; khi đặt, middleware ghi nhận **cả** API key **cả** JWT hợp lệ (phủ toàn bộ route ghi) và `POST /backtests` ép vai trò ANALYST/ADMIN; để trống = token demo + danh tính ADMIN offline |
| `SCHEDULER_NEWS_SOURCE` / `SCHEDULER_NEWS_INTERVAL_MINUTES` | provider tin (mặc định `cafef`) + chu kỳ (mặc định `15` phút) |
| `SCHEDULER_EOD_SOURCE` / `SCHEDULER_EOD_CRON_HOURS` / `SCHEDULER_EOD_CRON_MINUTE` / `SCHEDULER_EOD_LOOKBACK_DAYS` | nguồn EOD **chính** (mặc định `ssix_finipro`; job tự chuyển `yahoo → vndirect → tcbs → dsc`) · Thứ 2–6 **11:30 & 15:30** ICT (`11,15`/`30`) · cửa sổ nạp lại idempotent (`7` ngày) |
| `SCHEDULER_EOD_INDICES` / `SCHEDULER_EOD_INCLUDE_INTRADAY_SESSION` | mã chỉ số nạp kèm EOD (mặc định `VNINDEX,VN30`; rỗng = bỏ qua) · `true` = giữ ảnh chụp phiên sáng 11:30 cho báo 12:30 (bị lượt 15:30 ghi đè), `false` = chỉ nạp phiên đã đóng (KI-014) |
| `SCHEDULER_EOD_CATCHUP_HOUR` / `SCHEDULER_EOD_CATCHUP_MINUTE` / `SCHEDULER_SESSION_CLOSE_HOUR` / `SCHEDULER_SESSION_CLOSE_MINUTE` | `15`/`50` = job `daily_eod_catchup` chỉ nạp lại khi dữ liệu cũ hơn phiên đã đóng · `15`/`15` = mốc đóng phiên (ICT) cho catch-up và cảnh báo `intraday snapshot` (KI-014) |
| `SCHEDULER_SCORING_CRON_HOURS` / `SCHEDULER_SCORING_CRON_MINUTE` | job chấm điểm Thứ 2–6 **12:00 & 16:00** ICT (`12,16`/`0`), 30 phút sau mỗi lượt nạp EOD |
| `SCHEDULER_EMAIL_SYNC_MINUTES` | chu kỳ worker đọc lại `email_schedule_configs` (`15` phút) — lịch email sửa trên dashboard áp dụng hot, không cần restart |
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
- `python -m apps.worker.cli ingest --dataset financials --source cafef_financials --symbols FPT,VCB,HPG --period-types QUARTER` — **BCTC thật từ CafeF `apiweb` (kiểm chứng 2026-10-03)**: CĐKT + KQKD + LCTT, kỳ quý/năm. Ghi `financial_statements` với `published_at = NULL` (CafeF không trả ngày công bố → không bịa). Chạy lại là no-op (idempotent).
- `python -m apps.worker.cli ingest --dataset financials --source cafef_financials --symbols <30 mã VN30> --period-types QUARTER YEAR` — backfill VN30 (fact 2026-10-03: fetched=204065 written=190125 quality=99.58 → 201.402 dòng, 2005→2026)
- `python -m apps.worker.cli ingest --dataset financials --source vndirect_financials --symbols FPT,VCB --period-types QUARTER` — dự phòng VNDirect (**chưa kiểm chứng live**: finfo timeout từ host dev → `MAPPING_TO_VERIFY_2026-10-03`)
- `python -m apps.worker.cli ingest --dataset financials --source fixture --symbols FPT,VCB` — ETL BCTC offline (fixture: 8 quý × 5 chỉ tiêu, `published_at` = cuối quý + 45 ngày)
- `python -m apps.worker.cli ingest --dataset events --source yahoo --symbols <30 mã VN30> --since 2020-01-01T00:00:00+00:00` — **sự kiện doanh nghiệp thật (cổ tức + tách cổ phiếu)** từ Yahoo `events=div,split` (kiểm chứng 2026-10-03: written=238); dedup `(stock_id, event_type, event_date)`
- `python -m apps.worker.cli ingest --dataset macro --source imf_worldbank --start 2010-01-01 --end 2026-12-31` — **vĩ mô thật** (GDP growth + CPI inflation, IMF datamapper; kiểm chứng 2026-10-03: written=32, chỉ năm đã kết thúc); tuỳ chọn `--indicators GDP_GROWTH_PCT`
- `python -m apps.worker.cli ingest --dataset events --source fixture --symbols FPT,VCB --since 2026-01-01T00:00:00+00:00` — sự kiện doanh nghiệp offline (fixture; chạy lại không tạo bản ghi trùng)
- `python -m apps.worker.cli backtest-strategy --profile mid --top-n 5 --rebalance-days 21 --start 2025-10-01 --end 2026-09-30 --symbols <30 mã VN30>` — **backtest module điểm (GĐ 5)**: mỗi ngày rebalance chấm điểm **as-of** rồi vào top-N tại giá mở cửa phiên kế tiếp (không look-ahead), có phí + trượt giá; in bảng so sánh với VNINDEX mua & giữ. Fact 2026-10-03: short −15.22% / mid −17.09% / long −14.44% vs **VNINDEX +6.22%** → cả 3 thua chỉ số (vòng quay 9.8–17.5×/năm). Chi tiết + đề xuất: `docs/strategy_backtest_report_vi.md`
- `python -m apps.worker.cli strategy-scores --symbols <mã> --as-of 2026-10-03` — **chấm điểm 3 chiến lược (GĐ 4)**: đọc điểm 7 nhóm → `score_profile` cho short/mid/long → grade A–D + vùng mua/cắt lỗ/mục tiêu (ATR) + lý do/rủi ro tiếng Việt + disclaimer §3; ghi `strategy_scores` + `strategy_recommendations`. Fact 2026-10-03: 30 mã VN30 → scored=90 written=90 (mid: A=1 B=2 C=9 D=18).
- `python -m apps.worker.cli notify-strategy-changes [--dry-run]` — **cảnh báo đổi grade (GĐ 6)**: so 2 phiên chấm điểm gần nhất, gửi email (dùng SMTP đã cấu hình ở trang Quản lý Email) chỉ khi **có thay đổi**; không gửi gì khi <2 phiên hoặc không có đổi. `--dry-run` chỉ dựng HTML để xem trước.
- `python -m apps.worker.cli compute-features --symbols <mã> --as-of 2026-10-03` — **feature engine (GĐ 3)**: tính 24 chỉ số + điểm 7 nhóm (percentile 0–100, áp `direction`) và ghi bảng `features` (`grp:<nhóm>` cho điểm nhóm). Fact 2026-10-03: 30 mã VN30 → written=761. Chống look-ahead: BCTC chỉ dùng từ `published_at` hoặc `report_date + 45/90 ngày` (`configs/strategy_features.yaml`).
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

## API (T010 + T016 + T018; 48 đường dẫn / 53 thao tác trên `/api/v1/*`, 2026-09-28)

- **Framework:** FastAPI 0.115 · endpoint `/api/v1/*`, tiền tố `docs/api.html`.
- **Router:** 13 tệp — nhóm market (+ `/indices/{code}/prices`, `/movers`), stocks (+ `?vn100=`), fundamentals, technical, valuation, news, backtests, rag/evidence, agents/analysis, predictions, monitoring, auth, **notifications** (CRUD recipients, smtp, schedule, send-test, preview-html, logs — 11 thao tác, T018).
- **Service:** protocol `MarketSource` (`apps/api/services/market_source.py`, 23 phương thức) — `MarketService` trong bộ nhớ, tất định (mặc định; KI-008 phần đọc đã mở) hoặc `DbMarketService` đọc TimescaleDB khi `MARKET_DATA_SOURCE=db|auto`; `/readyz` trả `market_source` dạng `<chế độ>-><service>`. Để mở rộng: nối repository SQLAlchemy mới vào `DbMarketService`, không đụng router.
- **Probe sẵn sàng:** `/healthz` (liveness tĩnh) và `/readyz` dò thật — `database` (`connected`/`connected-no-prices`/`unreachable`), `qdrant` (`up`/`offline-index-ready`), `agents` (`llm:<model>`/`offline:<tasks>`), `models` (`<model_id>@<version>` nạp từ `model_registry`, hoặc `stub`), `market_source` (live: `auto->db`); probe luôn trả 200 (không 5xx). Prebuilt image đã cài extra `[qdrant]` (client Qdrant, không có torch) để mirror `dtck_docs` chạy thật.
- **Registry mô hình (T015b):** `train-model --source db` lưu pickled `ModelEntry` vào `model_registry.artifact`; API nạp lại qua `lifespan` (`src/ml/registry_store.py`) nên `/predictions` phục vụ model thật thay vì stub. Bảng có `target`/`horizon_days`; chu kỳ huấn luyện để NULL (không bịa theo §31).
- **Chiều ghi Backtest (T015b):** `POST /api/v1/backtests` chèn bản ghi vào `backtests` khi chạy DB mode (chi phí mặc định 15/5 bps); `GET /backtests*` phục vụ lại đúng bản ghi đó.
- **Thông báo email (T018, mở rộng 2026-09-28):** `NotificationService` (`src/notifications/service.py`) + 4 bảng, validation regex email stdlib (không `email-validator`), cảnh báo password Gmail ≠ 16 ký tự (không phải App Password); lỗi SMTP (535/disconnect/recipient) được map sang tiếng Việt hành động được. **3 khung báo cáo** mỗi ngày (Mon–Fri, `Asia/Ho_Chi_Minh`): 08:00 tổng kết phiên trước, 12:30 phiên sáng, 16:30 phiên chiều → job APScheduler `daily_morning_email_report` / `daily_noon_email_report` / `daily_afternoon_email_report`. Giờ gửi đọc từ `email_schedule_configs` (`DEFAULT_EMAIL_SCHEDULE` khi bảng rỗng/CSDL không truy cập được) và được đồng bộ lại mỗi `SCHEDULER_EMAIL_SYNC_MINUTES` (15') nên sửa trên dashboard áp dụng ngay → scheduler **8 job** (thêm `daily_eod_catchup` 15:50, KI-014).
- **Schemas:** 24 lớp Pydantic trong `apps/api/schemas.py`, gồm `Page[T]` generic + `ErrorResponse` (+ `MoversOut`, schema notifications trong router).
- **Kiểm thử:** `pytest tests/unit/test_api.py` (health/readyz, nhóm router, notifications, phân trang, 404) + `tests/unit/test_market_data_source.py` (protocol 23 phương thức) + `tests/unit/test_email_notifications.py` (9 bài) + integration `tests/integration/test_email_notifications.py` (9 bài; chạy qua fixture `isolated_session_factory` — transaction rollback, không chạm CSDL thật). **Mới 2026-09-29 (KI-014):** `tests/unit/test_freshness.py` (9 bài: `expected_session_date`/`stale_datasets`/`is_intraday_snapshot`) + `tests/integration/test_freshness.py` (2 bài, đọc `max(trade_date)`/`ingested_at` thật) + 11 bài trong `tests/unit/test_worker_scheduler.py` (catch-up, nạp chỉ số, cảnh báo `intraday snapshot`).
- **Kiểm chứng số liệu (2026-09-28):** con số lấy từ `app.openapi()` — 48 đường dẫn / 53 thao tác trên `/api/v1/*`; cộng `/healthz` + `/readyz` + `/metrics` thành 51 đường dẫn / 56 thao tác. Các ghi chú cũ "39 đường dẫn / 40 thao tác" là trước khi thêm `notifications` (T018) và các endpoint T016.

## Quy trình cập nhật phụ thuộc

Khi `pyproject.toml`/`requirements*.txt` thay đổi → làm mới wheel trong `offline_package/` và cập nhật tệp này (quy tắc §2.4).

> Ghi chú: `PyYAML` đã được cài vào venv cục bộ để chạy (không bỏ qua) `tests/unit/test_sources_registry.py`
> (T002) nhưng **chưa** là phụ thuộc dự án — `pyproject.toml` không đổi. Nếu bạn đồng ý
> thêm `pyyaml` vào `[project.optional-dependencies] dev`, test registry cũng chạy được trong Docker/CI.
