# Bộ nhớ dự án — Task đang làm (Bản tiếng Việt)

> Thuật ngữ chuyên môn (tên bảng, biến môi trường, lệnh, đường dẫn) giữ nguyên tiếng Anh.

## Task: T019 — Thiết kế lại giao diện Dashboard chuẩn BI tài chính chuyên nghiệp

**Trạng thái:** HOÀN THÀNH (2026-09-28)
**Mục tiêu:** Nâng cấp toàn diện thẩm mỹ Streamlit dashboard DTCK sang phong cách tài chính BI chuẩn mực (Bloomberg / Refinitiv inspired, palette chuyên nghiệp, typography phân cấp rõ ràng, loại bỏ emoji chrome, SVG icons, thống nhất layout biểu đồ Plotly).

### Sản phẩm:
- [x] `apps/dashboard/theme.py`: Design tokens, dark sidebar / light surface CSS sheet, builder hàm HTML an toàn (`app_bar`, `page_header`, `section_label`, `side_card`, `brand_html`, `footer`), inline SVG icon path registry.
- [x] `apps/dashboard/app.py`: Gỡ bỏ emoji trong danh mục trang điều hướng; tích hợp `theme.page_header` trên toàn bộ 8 trang; áp dụng `theme.chart_layout` và cấu hình token cho toàn bộ các biểu đồ Plotly (candlestick, MA lines, volume, bar chart, score breakdown); thêm `theme.footer` với disclaimer §3 và dependency chips.
- [x] `tests/unit/test_dashboard_theme.py`: 17 unit test kiểm chứng tokens, SVG generator, HTML builders, CSS injection, Plotly config.
- [x] `tests/unit/test_dashboard_app.py`: Cập nhật và bổ sung 9 test headless AppTest kiểm tra render 8/8 trang không lỗi và hoàn toàn sạch bóng emoji chrome.

### Kiểm chứng:
- Chạy toàn bộ test dashboard: **69/69 passed** (`test_dashboard_app.py`, `test_dashboard_theme.py`, `test_dashboard.py`).
- Cú pháp và kiểu dữ liệu: `ruff check`, `ruff format --check`, `mypy` đạt 100% không phát sinh cảnh báo hay lỗi.

---


## Task: T018 — Module gửi email tự động (Gmail SMTP) + Trang quản trị dashboard

**Trạng thái:** HOÀN THÀNH (2026-09-28)
**Mục tiêu:** (1) gửi email báo cáo Tổng quan tự động Thứ 2–6 lúc 08:00 và 15:30 qua Gmail SMTP; (2) trang **📧 Quản lý Email** trên dashboard quản lý người nhận, tài khoản SMTP, lịch gửi, gửi thử + preview.

### Sản phẩm:
- [x] `src/notifications/` — `report_generator.py` (HTML Tổng quan: KPI, Top 10 tăng/giảm vs MA20, VN30 + P(tăng 5D), disclaimer §3), `smtp_mailer.py` (stdlib: STARTTLS 587/SSL 465, map lỗi AUTH/disconnect/recipient sang tiếng Việt), `service.py` (`NotificationService`: recipients/SMTP/schedule/logs/dispatch).
- [x] `src/common/models/notifications.py` + migration `0003_email_notifications` (4 bảng; 42 bảng tổng).
- [x] Router `notifications` — 11 thao tác `/api/v1/notifications/*` (CRUD recipients, smtp, schedule, send-test, preview-html, logs).
- [x] Worker: 2 cron Mon–Fri **08:00** + **15:30** (`Asia/Ho_Chi_Minh`) → scheduler **5 job**.
- [x] Dashboard **📧 Quản lý Email** (5 tab: gửi thử/preview HTML, người nhận, SMTP Gmail, lịch gửi, logs); validation regex stdlib (không `email-validator`); cảnh báo password ≠ 16 ký tự (không phải App Password).

### Kiểm chứng (fact, 2026-09-28):
- **566 unit passed + 3 skipped** (569 thu thập) và **29 integration passed**; `ruff check` + `mypy` (**139 tệp**) sạch.
- Test integration ghi trong transaction rollback (`isolated_session_factory`) ⇒ **không** sửa/xoá dữ liệu thật; regression `test_isolated_writes_never_reach_the_shared_database` bảo vệ (KI-013).
- Live trong container: build HTML 16 KB từ service thật, worker đăng ký đủ 5 job (`daily_morning_email_report`, `daily_afternoon_email_report`), trace SMTP đến AUTH rồi 535 → map sang hướng dẫn App Password.
- **Còn chặn vận hành (phía người dùng, không phải bug repo):** Gmail yêu cầu App Password 16 ký tự cho SMTP (mật khẩu thường → 535; thử lại nhiều lần → Gmail đóng kết nối `SMTPServerDisconnected`). Người dùng tự tạo tại `myaccount.google.com/apppasswords` rồi lưu trên dashboard.

### Bối cảnh đã đóng góp (giữ nguyên cho truy vết):
- T016 (Universe VN100/đa sàn + nến VNINDEX + Top 10 + login JWT, 2026-09-27): +11 bài ⇒ **510 unit, 20 integration**, ruff+mypy 133 tệp.
- T018 (2026-09-27): +11 bài ⇒ **521 unit, 28 integration**, ruff+mypy 138 tệp.
- `a39e130` (2026-09-28): map lỗi SMTP sang hướng dẫn App Password + cảnh báo password; +2 bài ⇒ **523 unit, 28 integration**.

---

## Task: T015c — Dashboard dùng dữ liệu thật + Bảng Đánh giá & Dự đoán VN30 + Form Backtest

**Trạng thái:** HOÀN THÀNH (2026-09-27)
**Mục tiêu:** (1) dashboard phải đọc dữ liệu **thật** từ API/CSDL thay vì fixture giả; (2) trình bày đánh giá + dự đoán xu hướng VN30 kèm bằng chứng đáng tin cậy để hỗ trợ quyết định đầu tư; (3) form nhập thông tin backtest; (4) giao diện chuyên nghiệp hơn.

### Nguyên nhân "dữ liệu giả" (đã sửa cả 4):
- [x] `client.py` gọi URL **literal** `{symbol}` → 404 → fallback fixture. Sửa: f-string URL thật + `_fallback` chuẩn hoá mã về template.
- [x] `list_stocks` thiếu `limit` (API mặc định 20/30 mã) → `limit=200`.
- [x] Sidebar hardcode `http://localhost:8000` (container tự gọi chính nó) → đọc `API_HOST` (`DEFAULT_BASE`).
- [x] `./apps/dashboard` chưa bind-mount → thêm vào `docker-compose.yml`.

### Trình bày mục tiêu hệ thống:
- [x] **Tổng quan:** bảng Đánh giá & Dự đoán VN30 (điểm §12 + tín hiệu + **P(tăng 5D) từ model thật** + Gợi ý 🟢/🟡/🔴 tất định + chú giải + footer disclaimer §3), KPI 5 thẻ, Top-10 biểu đồ màu theo tín hiệu.
- [x] **Chi tiết mã:** nến + MA20/MA50 + volume (6 tháng/1 năm/2 năm), chỉ báo §2.4 đủ 15 chỉ báo, khối Dự đoán ML, nút Phân tích AI (thesis + catalysts + risks từ Ollama), Bằng chứng RAG §19.
- [x] **Backtest:** form tạo lượt chạy (chiến lược/vũ trụ/loại/khoảng ngày → `POST /api/v1/backtests`), danh sách nhãn dễ đọc, chỉ số §16 đúng đơn vị.
- [x] **Bộ lọc:** đủ 30 mã VN30 + tìm kiếm theo mã/tên + lọc sàn.
- [x] **Giao diện:** banner gradient, sidebar tối, thẻ KPI viền xanh, bảng bo góc, nav 7 trang unified, footer trạng thái.

### Kiểm chứng trực tiếp (fact, 2026-09-27):
- Container dashboard → API thật: `stocks=30 transport=api`, `FPT prices=496 bars` (đến 2026-09-25), `inds=15 chỉ báo`, `prediction FPT P=0.5058 model v1.0.0`, `ranked=30`.
- AppTest headless trong container với API thật: **7/7 trang render không exception**.
- Bộ test: **499 unit + 20 integration passed**; ruff + mypy (133 tệp) sạch.

---

## Task: T015b — Bền vững hoá ML registry, backfill dữ liệu 2 năm, vận hành tự động & hoàn thiện API

**Trạng thái:** HOÀN THÀNH (2026-09-27)
**Mục tiêu:** (2) model đã huấn luyện phải sống sót qua tiến trình và được API phục vụ thật; (3) nạp lịch sử đủ dài để backtest/ML có ý nghĩa; (4) sao lưu + CI + cảnh báo; (5) sửa lỗi làm tròn payload điểm và nối chiều ghi `POST /backtests` vào CSDL.

### Các công việc đã thực hiện:
- [x] **#2 Registry bền vững** — migration `0002_model_registry_artifact` (`artifact BYTEA`, `target`, `horizon_days`; chu kỳ huấn luyện nullable), `src/ml/registry_store.py` (`save_entry`/`load_entries`/`hydrate_default_registry`), CLI lưu sau khi fit, API `lifespan` nạp lúc khởi động, `/readyz.models`.
- [x] **#3 Backfill + sửa lỗi upsert** — `_UPSERT_CHUNK=1000` trong `src/data/pipelines.py` (lỗi 65.535 tham số truy vấn), nạp 14.810 dòng VN30 2 năm, huấn luyện lại trên 14.066 mẫu.
- [x] **#4 Vận hành** — `scripts/backup_db.sh`, `scripts/health_alert.sh`, `.github/workflows/ci.yml`, `backups/` trong `.gitignore`, mount `./apps` cho container.
- [x] **#5a Làm tròn** — dồn phần dư vào thành phần lớn nhất (`apps/api/services/ranking_payload.py`).
- [x] **#5b JWT/RBAC** — `apps/api/security.py` (HS256 stdlib), login cấp JWT thật với `AUTH_JWT_SECRET`, middleware nhận cả API key cả JWT hợp lệ, `POST /backtests` ép ANALYST/ADMIN.
- [x] **#5c Ghi backtest** — `POST /api/v1/backtests` chèn hàng thật khi DB mode.
- [x] **Kiểm thử** — 491 unit + 20 integration pass; ruff + mypy (133 tệp) sạch.
- [x] **Tài liệu** — `memory-bank/{tasks,known-issues,changelog,current-state,active-task}_vi.md`, `helper/{resources,deployment}_vi.md`, `docs/{DEPLOYMENT,SECURITY}_vi.md`.

### Kiểm chứng trực tiếp (fact đã đo, 2026-09-27):
- `train-model --source db` → `persisted: true`, `roc_auc=0.583` (14.066 hàng); `psql`: `artifact_bytes=64200`, `status=APPROVED`.
- `curl /readyz` → `{"market_source":"auto->db","dependencies":{"database":"connected","qdrant":"up","agents":"llm:qwen3.5","models":"price_direction_xgb@1.0.0"}}`.
- `GET /api/v1/predictions/VCB` → 200 với model đã huấn luyện (`probability_positive=0.5025`) thay vì stub.
- Backfill: `prices` = 14.816 dòng, 30 mã, 2024-09-27 → 2026-09-25; 8 cảnh báo OHLC trên TPB.
- `scripts/backup_db.sh` → `backups/dtck_20260927_110245.sql.gz` (345 KB); `scripts/health_alert.sh` → OK (DB=connected).
- Làm tròn đóng góp: sai lệch tối đa **1e-4 → 0.0**.
- `POST /api/v1/backtests` (DB mode) → 201 + hàng trong `backtests`.

---

## Task: T015a — Production hardening: API-key auth + `/metrics` + `train-model --source db`

**Trạng thái:** HOÀN THÀNH (2026-09-27)
**Mục tiêu:** (a) cổng API-key cho endpoint thay đổi trạng thái & `/metrics` (§32); (b) endpoint Prometheus `/metrics` cho độ trễ request + thời gian chạy agent (§46); (c) mở khóa huấn luyện ML thật (`train-model --source db`, đóng KI-012).

### Các công việc đã thực hiện:
- [x] **API-key auth** — `apps/api/middleware.py::ApiKeyAuthMiddleware` (ASGI): khi `API_AUTH_KEY` đặt, mọi POST/PUT/PATCH/DELETE dưới `/api/v1/` (trừ `/auth/login`) + `GET /metrics` cần `Authorization: Bearer <key>` (`secrets.compare_digest`); sai → 401 phong bì §2.1 + `WWW-Authenticate`. Key rỗng = tắt (mặc định — demo/test không đổi). Nối: `api_auth_key` (`apps/api/config.py`), `docker-compose.yml`, `.env`, `.env.example`.
- [x] **`/metrics` thuần stdlib** — `apps/api/metrics.py` (Prometheus text 0.04, thread-safe, histogram 11 bucket): `dtck_http_requests_total`, `dtck_http_request_duration_seconds`, `dtck_agent_runs_total`, `dtck_agent_duration_seconds`. `MetricsMiddleware` gắn nhãn **route template** (không lộ path thô); agent sync + async ghi qua `_observe_run`/`_execute_observed` (`apps/api/routers/agents.py`); endpoint `GET /metrics` (`apps/api/main.py`). Không thêm dependency `prometheus_client`.
- [x] **`train-model --source {memory,db}`** — `apps/worker/cli.py::_train_market_service` + cờ `--source` (mặc định `memory`); `db` → `DbMarketService`. **Đóng KI-012.**
- [x] **Sửa fallback EOD (bug live tìm thấy)** — SSI kiểm tra credential trễ lúc lấy token → `ingest_eod` ném ngoài `try` hủy cả chuỗi dự phòng; nay toàn bộ gọi nằm trong `try` của vòng lặp nguồn (`apps/worker/main.py`).
- [x] **Kiểm thử (+17)** — `tests/unit/test_t015_hardening.py` (16) + `test_worker_scheduler.py` (1: fallback khi fetch ném lỗi). ⇒ **459 passed, 3 skipped**; ruff sạch; mypy 131 tệp sạch.
- [x] **Tài liệu** — `docs/DEPLOYMENT_vi.md`, `helper/resources_vi.md`, `memory-bank/{changelog,tasks,known-issues,current-state}_vi.md`.

### Kiểm chứng trực tiếp (fact đã đo, 2026-09-27):
- Auth (với `API_AUTH_KEY=live-test-key`): POST không key **401** · key sai **401** · key đúng **200** · GET `/api/v1/stocks/ranked` **200** · `/auth/login` **200** · `/metrics` không key **401** / có key **200** · `/healthz` **200**.
- `POST /api/v1/agents/analyze VCB` (Ollama `qwen3.5` thật) → `succeeded`, `latency_ms=14186`; `/metrics` ghi `dtck_agent_runs_total{status="succeeded",task="analyze"} 1`.
- `train-model --source db` → 616 hàng, `roc_auc=0.702256`, `brier=0.225`, `price_direction_xgb v1.0.0 APPROVED`.
- Job EOD (sau sửa): `ssix_finipro failed: missing SSI_CONSUMER_ID…` → **yahoo `fetched=147 written=147 quality=92.78`**.
- Job scoring: `factor_scores` = 4 dòng `baseline_1.0`, as-of 2026-09-25. Job news: `fetched=1 skipped=1 quality=95.38`.
- `curl /readyz` → `{"market_source":"auto->db", "database":"connected","qdrant":"up","agents":"llm:qwen3.5"}`.

### Ghi chú vận hành:
- **`.env` từng bị reset về bản sao `.env.example` (00:44)** — đã khôi phục cấu hình không secret (`MARKET_DATA_SOURCE=auto`, Ollama `local`/`qwen3.5`/`host.docker.internal:11434`); **`SSI_CONSUMER_ID`/`SSI_CONSUMER_SECRET` phải được nhập lại** — EOD đang tự dự phòng Yahoo nên hệ thống vẫn chạy.
- Shell máy chủ export `MARKET_DATA_SOURCE=memory` (override `.env` khi compose nội suy) — khi `docker compose up` cần truyền `MARKET_DATA_SOURCE=auto` tường minh.
- Bật khóa bằng cách đặt `API_AUTH_KEY` trong `.env` rồi `docker compose up -d --force-recreate api`.

---

## Task: T017 — SSI FastConnect là nguồn chính (Yahoo dự phòng) + `/readyz` báo đúng thực tế

**Trạng thái:** HOÀN THÀNH (2026-09-27)
**Mục tiêu:** (a) đưa SSI FastConnect thành nguồn dữ liệu thị trường **chính** với chuỗi dự phòng tự động về Yahoo; (b) trả lời trung thực câu hỏi "hệ thống đã sẵn sàng chưa" ở `/readyz` (bỏ giá trị hardcode `pending`/`offline:…`).

### Các công việc đã thực hiện:
- [x] **Chuỗi nhà cung cấp** — `src/data/providers/registry.py::market_provider_chain(primary)`: nguồn chính trước, rồi `fallback_chains.market`, khử trùng lặp ⇒ `[ssix_finipro, yahoo, vndirect, tcbs, dsc]`; export qua `src/data/providers/__init__.py` + `src/data/__init__.py`.
- [x] **Dự phòng trong job EOD** — `apps/worker/main.py::scheduled_eod_ingestion()` đi hết chuỗi: nguồn không dựng được (thiếu credential) hoặc trả 0 dòng ⇒ log WARNING + thử nguồn kế tiếp; hết chuỗi ⇒ ERROR. `SCHEDULER_EOD_SOURCE` mặc định `ssix_finipro` (`apps/api/config.py`, `docker-compose.yml` ×2, `.env.example`).
- [x] **`/readyz` trung thực** — `apps/api/main.py`: `_database_status()` (connected / connected-no-prices / unreachable), `_qdrant_status()`, `_agents_status()` (`llm:<model>` | `offline:<tasks>`), `_market_source_status()` (`<chế độ>-><service>`), thêm khoá `market_source`; probe best-effort không ném 5xx.
- [x] **Qdrant trong image** — extra `[qdrant]` trong `pyproject.toml` (chỉ client, pin trùng `[rag]`), `docker/Dockerfile.api` + `Dockerfile.worker` cài `.[dev,ml,qdrant]`.
- [x] **Kiểm thử (+12)** — `test_sources_registry.py` (2), `test_worker_scheduler.py` (2), `test_api.py` (4), `test_deployment_config.py` (3, có test chống trôi pin).
- [x] **Tài liệu** — `docs/DATA_SOURCES_vi.md`, `docs/DEPLOYMENT_vi.md`, `docs/api.html`, `docs/status.html`, `docs/modules.html`, `docs/pipeline.html`, `helper/deployment_vi.md`, `helper/resources_vi.md`, `memory-bank/{changelog,decisions,known-issues,current-state,tasks,active-task}_vi.md`, `configs/sources.yaml` (`VERIFIED_2026-09-27`).

### Kiểm chứng trực tiếp (fact đã đo, 2026-09-27):
- `curl /readyz` → `{"status":"ready","market_source":"auto->db","dependencies":{"database":"connected","qdrant":"up","agents":"llm:qwen3.5"}}`
- `ingest --dataset prices --source ssix_finipro --symbols FPT,VCB,HPG,ACB --start 2026-09-01 --end 2026-09-26` → `fetched=68 written=68 issues=0 quality=93.74`
- `ingest --dataset index_prices --source ssix_finipro --indexes VNINDEX,VN30 --start 2026-09-01 --end 2026-09-26` → `fetched=34 written=34 quality=93.74`
- CSDL: 716 dòng `prices` (source `ssix_finipro`) · 34 dòng `index_prices`; Qdrant: collection `dtck_docs`, `GET /rag/status` → `qdrant_available: true`
- Suite: `LLM_PROVIDER=mock MARKET_DATA_SOURCE=memory pytest tests/unit -q` → **442 passed, 3 skipped**; `ruff` sạch; `mypy apps src` → 129 tệp sạch; `docker compose build api worker` thành công.

### Ghi chú vận hành:
- `docker compose build api worker` **bắt buộc** sau thay đổi này (Dockerfile + code job).
- Credential SSI: `SSI_CONSUMER_ID` + `SSI_CONSUMER_SECRET` trong `.env` (đổi JWT qua `Market/AccessToken`); `FINIPRO_ACCESS_TOKEN` có thể để trống.
- Nếu SSI hết hạn ngạch/lỗi, job tự chuyển Yahoo — không cần đổi cấu hình; log sẽ ghi `EOD source '…' … trying the next source`.

---

## Task: T016 — Nối tầng suy luận LLM local (Ollama) cho Analysis Agent

**Trạng thái:** HOÀN THÀNH (2026-09-26)
**Mục tiêu:** Cho Analysis Agent sinh `thesis` tiếng Việt từ Ollama `qwen3.5` (ADR-005) **không** đổi dữ liệu quant, có fallback tất định, và giữ nguyên bộ test offline.

### Các công việc đã thực hiện:
- [x] **Tầng provider LLM** — tạo `src/agents/llm/` (`LLMClient` Protocol `@runtime_checkable`, `MockLLMClient`, `OllamaLLMClient` dùng `httpx` + `transport` để test không cần mạng, `create_llm_client`).
- [x] **Nối vào agent** — `AnalysisAgent(llm=...)` + `_synthesize_llm_thesis()` (prompt gồm điểm đa yếu tố, điểm thành phần, giá, regime, catalysts, risks, tin tức; chỉ thay `thesis`; lỗi/timeout/rỗng ⟶ mẫu tất định); `Orchestrator(llm=...)` truyền xuống và gắn nhãn audit `deterministic-quant-v1+<model>`.
- [x] **Cấu hình** — `get_llm_client()` trong `apps/api/services/agent_service.py` (`mock` ⇒ `None`), `timeout_s = LLM_TIMEOUT_SECONDS + 15`, thêm `llm_think` vào `Settings` + `.env.example`/`.env` (`LLM_THINK=false`), ví dụ `local`/`qwen3.5`/`host.docker.internal:11434`.
- [x] **API** — `GET /api/v1/agents` trả thêm `llm_model` + `reasoning`.
- [x] **Test** — `tests/unit/test_llm_client.py` (22 test), `test_smoke` nhận alias `ollama`.
- [x] **Tài liệu** — `docs/AGENT_ARCHITECTURE_vi.md` §8.1, `docs/api.html`, `docs/modules.html`, `docs/index.html`, `docs/structure.html`, `docs/DEPLOYMENT_vi.md`, `helper/deployment_vi.md`, `helper/resources_vi.md`, `memory-bank/{changelog,tasks,current-state}_vi.md`.
- [x] **Kiểm chứng trực tiếp** — rebuild image `api` → `docker compose up -d api`; từ host: `POST /api/v1/agents/analyze` `VCB` `succeeded` `latency_ms≈15000` `model=deterministic-quant-v1+qwen3.5`; async `HPG` `succeeded` 12,1 s; bộ test `LLM_PROVIDER=mock MARKET_DATA_SOURCE=memory pytest` → **449 passed, 3 skipped, 1 failed có sẵn**; `ruff` + `mypy` (129 tệp) sạch.

### Ghi chú vận hành (fact đã đo):
- Ollama máy host đã `OLLAMA_HOST=0.0.0.0` (systemd override) → container qua `host.docker.internal:11434` OK.
- `think=false` **bắt buộc** với `qwen3.5`: nếu bật, khối suy luận chiếm hết `num_predict` nên `response` rỗng và mất 30–170 s. Với `think=false`: ~12–22 s/luận điểm.
- `qwen2.5-7b-65k:latest` (~5–11 s) là lựa chọn nhanh hơn nếu cần độ trễ thấp hơn.
- Lỗi có sẵn ngoài phạm vi: `tests/integration/test_scoring_job::test_api_reader_serves_the_persisted_run` (`0.9999` vs `1.0`).

---

## Task trước: Chuẩn hóa 100% tài liệu tiếng Việt — Xóa bỏ các bản tiếng Anh & Ban hành quy ước tài liệu tiếng Việt

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
  → *Đã hết ở T016 (2026-09-26): allowlist của smoke test nhận thêm `ollama` như alias của `local`.*


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

