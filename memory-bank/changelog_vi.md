# Bộ nhớ dự án — Nhật ký thay đổi (Bản tiếng Việt)

> Thuật ngữ chuyên môn (tên bảng, biến môi trường, lệnh, đường dẫn) giữ nguyên tiếng Anh.

**Cập nhật lần cuối:** 2026-09-27

## 2026-09-27 — T015c: Sửa dashboard dùng dữ liệu thật + bảng dự đoán VN30 + form Backtest

- **Gốc rễ "dữ liệu giả" trên dashboard** — `apps/dashboard/client.py` từng gọi `self._get("/api/v1/stocks/{symbol}/prices", symbol=…)` với **URL literal `{symbol}`** → API trả 404 → client âm thầm rơi về fixture trong tiến trình (7 mã, giá giả). Sửa: URL f-string thật (`/api/v1/stocks/FPT/prices`) + `_fallback` tự chuẩn hoá mã về template cũ. Kèm: `list_stocks` mặc định `limit=200` (API mặc định 20 → screener chỉ hiện 20/30 mã), bind-mount `./apps/dashboard` vào container, sidebar đọc `API_HOST` thay vì hardcode `localhost:8000` (trước đây container tự gọi chính nó → fail → fixture).
- **Bảng "Đánh giá & dự đoán VN30" (mục tiêu hệ thống)** — trang Tổng quan gộp 3 nguồn theo từng mã: điểm định lượng §12 + tín hiệu, **P(tăng 5D) từ model ML thật** (`/predictions`, cache 120 s), và cột Gợi ý tất định (🟢/🟡/🔴 — không phải lệnh mua/bán, §3). Kèm chú giải cách đọc từng cột + disclaimer §3 trong footer.
- **Chi tiết mã đủ chứng cứ** — thêm khối "Dự đoán ML & đánh giá AI": P(tăng 5D)/LN kỳ vọng/độ tin cậy/model đang phục vụ, nút chạy Analysis Agent (LLM sinh thesis + catalysts + risks, ~15 s), và mục **Bằng chứng §19** (RAG: snippet + nguồn + confidence). Biểu đồ giá: nến + MA20/MA50 + khối lượng phụ đề, chọn 6 tháng / 1 năm / toàn bộ 2 năm (dữ liệu 496 bars thật).
- **Chỉ báo kỹ thuật §2.4 thật** — đường đọc `DbMarketService.get_indicators` chỉ công bố 3/15 chỉ báo. Nâng lên bộ đầy đủ: close, SMA20/50, EMA12/26, RSI14, MACD/signal/hist, Bollinger upper/middle/lower, ATR14, volume SMA20, price_vs_sma20 (đồng bộ `MarketService` để hai nguồn khớp hợp đồng).
- **Backtest có form nhập** — trang Backtest giờ có form tạo lượt chạy (chiến lược / vũ trụ / loại chạy / khoảng ngày) gọi `POST /api/v1/backtests`, hiển thị lỗi auth rõ ràng; danh sách lượt chạy hiển thị nhãn `strategy · start → end` thay vì UUID trần; chỉ số §16 định dạng đúng đơn vị (Sharpe không còn bị hiển thị "120%").
- **Giao diện** — banner gradient đầu trang, sidebar tối, thẻ KPI viền xanh + đổ bóng, bảng có viền bo góc, footer trạng thái hệ thống (`market_source`/DB/model/tác tử). Nav gộp 7 trang vào một radio thống nhất (bỏ checkbox rời rạc).
- **Kiểm thử** — mới `tests/unit/test_dashboard_app.py` (3 bài AppTest headless: boot không exception, đủ 7 trang, bảng dự đoán hiện diện) + kiểm chứng AppTest trong container với API thật (7/7 trang render, 30 mã, 496 bars, 15 chỉ báo). Cập nhật kỳ vọng bộ chỉ báo ở `test_api.py`, `test_agents.py`, `test_db_market.py`. Kết quả: **499 passed, 3 skipped** (unit) · **20 passed** (integration) · ruff + mypy (133 tệp) sạch.

## 2026-09-27 — T015b: Bền vững hoá ML registry, backfill 2 năm, sao lưu/CI, sửa làm tròn & ghi Backtest

- **#2 Model registry bền vững (§10.1/§40)** — migration `0002_model_registry_artifact` (cột `artifact BYTEA` + `target`/`horizon_days`, gỡ NOT NULL chu kỳ huấn luyện — không bịa ngày theo §31, idempotent vì `0001` dùng `create_all`). `src/ml/registry_store.py`: `save_entry` (upsert `ON CONFLICT (model_id, version)` + pickle `ModelEntry`), `load_entries` (bỏ qua hàng hỏng kèm cảnh báo), `hydrate_default_registry`. `apps/worker/cli.py` lưu artifact sau khi fit (`"persisted": true`). `apps/api/main.py` chuyển sang **lifespan** nạp registry lúc khởi động (fail-soft) và `/readyz` thêm khoá `models`. Kiểm chứng live: `model_registry` có hàng 64.200 byte artifact; `curl /readyz` → `"models":"price_direction_xgb@1.0.0"`.
- **#3 Backfill 2 năm VN30 (đóng KI-009)** — phát hiện + sửa lỗi Postgres **65.535-tham số** (14.810 dòng × 10 cột trong một `INSERT`) bằng upsert chia lô `_UPSERT_CHUNK = 1000` trong `src/data/pipelines.py` (áp dụng cho cả `prices` và `index_prices`). Nạp trọn 30 mã VN30 `2024-09-27 → 2026-09-27`: **fetched=14810 written=14810 issues=8 quality=91.87**; CSDL hiện **14.816 dòng `prices`**. Huấn luyện lại `--source db`: 14.066 hàng → `roc_auc=0.583`, `accuracy=0.563`, `f1=0.502` (so với 0.702/616 hàng của tập nhỏ — con số thực tế hơn nhiều trên 2 năm).
- **#4 Vận hành** — `scripts/backup_db.sh` (pg_dump + gzip + retention, đã chạy thử → 345 KB), `scripts/health_alert.sh` (kiểm tra `/healthz` + `/readyz`, exit≠0 khi có sự cố), `.github/workflows/ci.yml` (ruff + mypy + `pytest tests/unit` offline), `.gitignore` thêm `backups/`, `docker-compose.yml` mount thêm `./apps` cho api/worker để sửa code không cần rebuild.
- **#5a Sửa lỗi làm tròn phân rã điểm** — `apps/api/services/ranking_payload.py`: `contribution_pct` làm tròn độc lập từng thành phần gây tổng 0.9999 (đo live: lệch tới **1e-4**). Nay phần dư được dồn vào thành phần lớn nhất khi vector *trước* làm tròn đúng bằng 1 → tổng chính xác 1.0 (đo lại: lệch **0.0**), vector thiếu thành phần giữ nguyên. Test: 2 bài trong `test_market_data_source.py`; test tích hợp từng fail nay pass.
- **#5c Ghi Backtest vào CSDL (KI-008 chiều ghi)** — `POST /api/v1/backtests` giờ chèn hàng thật vào `backtests` khi service là `DbMarketService` (UUID, chi phí mặc định 15/5 bps, `params` rỗng); chế độ memory giữ payload tất định. Kiểm chứng live: 201 + hàng `momentum_breakout_v1` trong CSDL.
- **#5b JWT/RBAC (§3/§32)** — `apps/api/security.py`: JWT HS256 **thuần stdlib** (`hmac`/`hashlib`/`base64`, không thêm phụ thuộc): `create_token`/`decode_token` (chữ ký + `exp` + `compare_digest`), `get_current_user` (machine API key → JWT → danh vị ADMIN offline), `require_roles` (401 → 403). `POST /api/v1/auth/login` cấp access (1 h) + refresh (7 ngày) khi `AUTH_JWT_SECRET` đặt, giữ token demo khi không. `ApiKeyAuthMiddleware` mở rộng: ghi nhận **cả** API key **cả** JWT hợp lệ (chữ ký bị kiểm tra ở middleware → token giả ký bị chặn trước mọi route ghi), khắc phục xung đột API-key-shadow-JWT. `POST /backtests` gắn `require_roles(ANALYST, ADMIN)` (RBAC §3). Biến mới `AUTH_JWT_SECRET`/`AUTH_JWT_TTL_SECONDS`/`AUTH_REFRESH_TTL_SECONDS` (`.env` đã sinh secret ngẫu nhiên, `.env.example` để trống). Kiểm chứng live: login JWT `role=ADMIN` · POST bằng JWT → **201** · JWT giả ký → **401** · không cred → **401** · GET mở → **200**.
- **Kiểm thử** — mới: `tests/unit/test_registry_store.py` (7), `tests/integration/test_model_registry_store.py` (2, upsert + hydrate), `tests/unit/test_security_jwt.py` (18: round-trip/tamper/hết hạn, RBAC 401/403/201, middleware gate), `tests/conftest.py` (tự động tắt `API_AUTH_KEY`/`AUTH_JWT_SECRET` để suite offline không bị 401), `test_api.py::test_readyz_reports_models`, 2 bài làm tròn. Kết quả: **491 passed, 3 skipped** (unit) · **20 passed** (integration) · ruff + mypy (133 tệp) sạch.

## 2026-09-27 — T015a: API-key auth + `/metrics` + `train-model --source db` (đóng KI-012)

- **API-key auth (§32)** — `apps/api/middleware.py::ApiKeyAuthMiddleware` (ASGI thuần): khi `API_AUTH_KEY` có giá trị, mọi POST/PUT/PATCH/DELETE dưới `/api/v1/` (trừ `/auth/login`) và `GET /metrics` phải kèm `Authorization: Bearer <key>`; so sánh bằng `secrets.compare_digest`; sai/thiếu → **401** phong bì `{error:{code:"unauthorized",…}}` + `WWW-Authenticate: Bearer`. Key rỗng (mặc định) = tắt hoàn toàn → demo offline và unit test không đổi hành vi; dashboard (chỉ GET) không bị ảnh hưởng. Biến mới `api_auth_key` (`apps/api/config.py`), nối qua `docker-compose.yml` (`API_AUTH_KEY: ${API_AUTH_KEY:-}`) + `.env`/`.env.example`.
- **`/metrics` (§46, thuần stdlib — không thêm `prometheus_client`)** — `apps/api/metrics.py` tự dựng text exposition Prometheus 0.04 (thread-safe, histogram 11 bucket): `dtck_http_requests_total{method,route,status}`, `dtck_http_request_duration_seconds{route}`, `dtck_agent_runs_total{task,status}`, `dtck_agent_duration_seconds{task}`. `MetricsMiddleware` đo latency mọi request và gắn **route template** (`scope["route"].path`) — path thô không lọt vào nhãn (không lộ symbol/thông số, không nổ cardinality). Agent ghi metric qua `_observe_run()` ở 4 endpoint sync + wrapper `_execute_observed` cho mẫu async (202 + poll). Endpoint `GET /metrics` trong `apps/api/main.py`.
- **`train-model --source {memory,db}` (đóng KI-012)** — `apps/worker/cli.py` thêm `_train_market_service(source)` + cờ `--source` (mặc định `memory` để unit test không cần hạ tầng); `db` dùng `DbMarketService`. Kiểm chứng live: 616 hàng · 21 đặc trưng · nhãn 369 âm / 247 dương · `roc_auc=0.702 brier=0.225 accuracy=0.629` · `price_direction_xgb v1.0.0 APPROVED`.
- **Sửa lỗi fallback EOD (tìm thấy khi kiểm chứng live)** — credential SSI được kiểm tra **trễ** lúc lấy token, nên `create_provider()` thành công nhưng `ingest_eod()` ném lỗi ngoài khối `try` → cả chuỗi dự phòng bị hủy thay vì chuyển Yahoo. Nay toàn bộ `ingest_eod()` nằm trong `try` của vòng lặp nguồn. Kiểm chứng live: `ssix_finipro failed: missing SSI_CONSUMER_ID…` → **yahoo fetched=147 written=147 quality=92.78**.
- **Kiểm thử** — mới `tests/unit/test_t015_hardening.py` (16 test: 401/401/200 cho key sai/đúng, GET mở, login mở, health mở, metrics gắt khi có key, route-label không lộ path thô, agent metric, shape exposition, parser `--source`) + `test_worker_scheduler.py` (+1: fallback khi fetch ném lỗi). Kết quả: **459 passed, 3 skipped** · `ruff` sạch · `mypy` 131 tệp sạch.
- **Kiểm chứng trực tiếp (2026-09-27)** — với `API_AUTH_KEY=live-test-key`: POST không key **401** · key sai **401** · key đúng **200** · GET `/stocks/ranked` **200** · `/auth/login` **200** · `/metrics` không key **401** / có key **200** · `/healthz` **200**. `/metrics` ghi agent run Ollama thật `task=analyze status=succeeded` (14,2 s). Job scoring ghi `factor_scores` (baseline_1.0, as-of 2026-09-25) và job news (`fetched=1 written=0 quality=95.38`) chạy trên CSDL thật.
- **Tài liệu** — `docs/DEPLOYMENT_vi.md` (lệnh `--source db`, mục Bảo mật & quan sát, roadmap KI-012 đóng, troubleshooting), `helper/resources_vi.md` (hàng `API_AUTH_KEY`), `memory-bank/{tasks,known-issues}_vi.md`.
- **Sự cố vận hành ghi nhận** — `.env` bị reset về bản sao của `.env.example` (00:44, mất credential SSI + `MARKET_DATA_SOURCE` + cấu hình Ollama); đã khôi phục cấu hình **không secret** (`auto`, `local`/`qwen3.5`/`host.docker.internal:11434`); **`SSI_CONSUMER_ID`/`SSI_CONSUMER_SECRET` phải được người dùng nhập lại** — EOD tự dự phòng Yahoo nên hệ thống vẫn chạy. Lưu ý: shell máy chủ export `MARKET_DATA_SOURCE=memory` nên khi chạy `docker compose up` phải truyền `MARKET_DATA_SOURCE=auto` (shell env thắng `.env` khi compose nội suy).

## 2026-09-27 — T017: SSI FastConnect là nguồn chính + dự phòng tự động + `/readyz` trung thực

- **Ưu tiên nhà cung cấp (SSI chính, Yahoo dự phòng)** — `src/data/providers/registry.py` thêm `market_provider_chain(primary=None)`: lấy `selection.market` (hoặc `primary` do người vận hành đặt) rồi nối `fallback_chains.market`, khử trùng lặp ⇒ `[ssix_finipro, yahoo, vndirect, tcbs, dsc]`. `apps/worker/main.py::scheduled_eod_ingestion()` đi hết chuỗi: nguồn **không dựng được** (ví dụ thiếu `SSI_CONSUMER_ID`/`SSI_CONSUMER_SECRET`) hoặc trả **0 dòng** ⇒ log WARNING và thử nguồn kế tiếp; hết chuỗi mới log ERROR. `SCHEDULER_EOD_SOURCE` mặc định đổi thành `ssix_finipro` (`apps/api/config.py`, `docker-compose.yml` × 2, `.env.example`) — `configs/sources.yaml` vẫn là nguồn sự thật duy nhất.
- **`/readyz` trung thực** — `apps/api/main.py` tách 4 hàm dò: `_database_status()` (`connected` / `connected-no-prices` / `unreachable`, dùng lại `apps/api/db.py::database_is_ready` — trước đây luôn trả `"pending"` hardcode), `_qdrant_status()` (`up` / `offline-index-ready`), `_agents_status()` (`llm:<model>` khi `LLM_PROVIDER=local`, ngược lại `offline:<tasks>` — trước đây luôn `offline:…` kể cả khi đã nối Ollama), `_market_source_status()` (`<chế độ>-><service>`), thêm khoá `market_source`. Probe không bao giờ ném lỗi (best-effort, ADR-001).
- **Qdrant trong image** — `pyproject.toml` thêm extra `[qdrant]` (chỉ `qdrant-client`, **không** kéo `sentence-transformers`/torch) với pin trùng `[rag]`; `docker/Dockerfile.api` + `Dockerfile.worker` cài `.[dev,ml,qdrant]`. Kiểm chứng: `docker compose exec api python -c "from src.rag.retrieval.store import QdrantAdapter; ..."` → `available: True`; `GET /rag/status` → `qdrant_available: true`, collection `dtck_docs`.
- **Kiểm chứng SSI đầu-cuối (live)** — `Market/AccessToken` đổi JWT từ credential consumer thật; `ingest --dataset prices --source ssix_finipro --symbols FPT,VCB,HPG,ACB --start 2026-09-01 --end 2026-09-26` → **fetched=68 written=68 issues=0 quality=93.74**; `ingest --dataset index_prices --source ssix_finipro --indexes VNINDEX,VN30` → **written=34**. CSDL sau đó: 716 dòng `prices` (source `ssix_finipro`) + 34 dòng `index_prices`. `configs/sources.yaml`: `ssix_finipro.endpoints_status = VERIFIED_2026-09-27`.
- **Kết quả `curl http://localhost:8000/readyz`** — `{"status":"ready","market_source":"auto->db","dependencies":{"database":"connected","qdrant":"up","agents":"llm:qwen3.5"}}` (trước: `pending` / `offline-index-ready` / `offline:analyze,monitor,portfolio,research`).
- **Kiểm thử** — thêm 12 bài: `test_sources_registry.py` (+2: thứ tự chuỗi SSI→Yahoo, override + khử trùng lặp), `test_worker_scheduler.py` (+2: dự phòng khi nguồn chính không dựng được / trả 0 dòng), `test_api.py` (+4: hình dạng `/readyz`, `database` không hardcode, `agents` theo LLM, `market_source`), `test_deployment_config.py` (+3: pin `[qdrant]` khớp `[rag]`, Dockerfile cài client). Kết quả: **442 passed, 3 skipped** · `ruff` sạch · `mypy` 129 tệp sạch.
- **Tài liệu** — `docs/DATA_SOURCES_vi.md` (bảng trạng thái + credential SSI consumer + thực thi chuỗi lúc chạy), `docs/DEPLOYMENT_vi.md` (readyz kỳ vọng, lệnh SSI 16/16b/16c, giai đoạn 4, troubleshooting), `docs/api.html` (hàng `/readyz`), `docs/status.html` (bảng tiến độ, KI-006/007/011, cấu hình `SCHEDULER_EOD_SOURCE`), `docs/modules.html` (`SSIFastConnectProvider`, `market_provider_chain`, `/readyz`, scheduler), `docs/pipeline.html`, `helper/deployment_vi.md`, `helper/resources_vi.md`, `memory-bank/*`.

## 2026-09-26 — T016: Nối tầng suy luận LLM local (Ollama) cho Analysis Agent

- **Tầng provider LLM (ADR-005)** — tạo mới `src/agents/llm/client.py` + `__init__.py`: `LLMClient` (Protocol `@runtime_checkable`, gồm `generate(...)` và nhãn `model`), `MockLLMClient`, `OllamaLLMClient` (POST `{base}/api/generate`, `stream=false`, `options.temperature/num_predict`, `think=false`, nhận `transport` để test không cần mạng theo mẫu `src/data/providers`), `create_llm_client(provider, ...)` nhận thêm `mock | local | ollama` (chưa hỗ trợ → fallback mock).
- **Nối vào agent** — `AnalysisAgent(tools, llm=...)`: khi có client, dựng prompt tiếng Việt từ chính dữ liệu tool (điểm đa yếu tố, điểm thành phần, giá, regime, catalysts, risks, tin tức) qua `_synthesize_llm_thesis()` và dùng văn bản trả về làm `thesis`. **Điểm số, evidence, catalysts, risks, confidence giữ nguyên**; LLM lỗi / timeout / trả rỗng ⟶ rơi về mẫu tất định (`logger.warning`). `Orchestrator(..., llm=...)` truyền client xuống và xuất nhãn audit `model` = `deterministic-quant-v1+<model>` (§13.2).
- **Cấu hình** — `apps/api/services/agent_service.py` thêm `get_llm_client()` (`lru_cache`; `LLM_PROVIDER=mock` ⇒ `None`, test không gọi mạng) và `get_orchestrator()` đặt `timeout_s = LLM_TIMEOUT_SECONDS + 15` khi bật LLM (nếu không, §45 sẽ cắt trước khi client kịp trả lời). `apps/api/config.py` thêm `llm_think: bool = False`; `.env.example` + `.env` thêm `LLM_THINK=false` và ví dụ `local`/`qwen3.5`/`host.docker.internal:11434`.
- **API** — `GET /api/v1/agents` thêm `llm_model` + `reasoning` (`llm` | `deterministic`) để người vận hành thấy tầng suy luận đang bật hay tắt.
- **Kiểm thử** — `tests/unit/test_llm_client.py` (22 test: factory, payload/think/HTTP error/timeout của Ollama qua `httpx.MockTransport`, luận điểm được thay bằng văn bản LLM trong khi quant không đổi, rơi về mẫu khi lỗi/rỗng, nhãn audit, wiring `get_llm_client`/`get_orchestrator`); `test_smoke::test_api_config_loads` nhận thêm cách đặt tên `ollama` (đã bật trong factory). 
- **Kiểm chứng trực tiếp (2026-09-26):** container `api` → `host.docker.internal:11434` (Ollama máy host, `OLLAMA_HOST=0.0.0.0`) thành công; `POST /api/v1/agents/analyze` → `VCB` `status=succeeded` `latency_ms≈15s` `model=deterministic-quant-v1+qwen3.5`, `thesis` tiếng Việt dựa trên 75/100 thực; async `POST /api/v1/analysis/request` → `HPG` `succeeded` 12,1s.
- **Tìm hiểu vận hành (fact):** `think=false` bắt buộc với `qwen3.5` vì chuỗi suy luận dùng hết ngân sách `num_predict` và làm `response` rỗng (~170 giây nếu bật). `qwen2.5-7b-65k` (~5–11 s) là phương án thay thế nhanh hơn.
- **Lỗi có sẵn (ngoài phạm vi):** `tests/integration/test_scoring_job::test_api_reader_serves_the_persisted_run` fails với tổng đóng góp `0.9999 ≠ 1.0 ± 1e-6` (renormalize chấm tròn) — có trước T016.
- **Lệnh test đúng:** `LLM_PROVIDER=mock MARKET_DATA_SOURCE=memory pytest` → **449 passed, 3 skipped, 1 failed (có sẵn)** — chạy trên máy chủ vì `tests/` **không** nằm trong image `api` (sửa lệnh sai trong `docs/DEPLOYMENT_vi.md` + `helper/deployment_vi.md` vốn chạy `docker compose exec api pytest` → 0 test).

## 2026-09-26 — D5: Chuẩn hóa 100% tài liệu tiếng Việt & Xóa bỏ các bản tiếng Anh

- **Chuẩn hóa ngôn ngữ tài liệu:** Chuyển đổi toàn bộ hệ thống tài liệu sang 100% tiếng Việt. Ban hành quy tắc: Từ nay khi cập nhật các file markdown của project chỉ sử dụng tiếng Việt và các file tiếng Việt.
- **Xóa bỏ các file tiếng Anh & file trùng lặp:**
  - Xóa 22 file tiếng Anh tương ứng trong `docs/` (12 file), `helper/` (2 file) và `memory-bank/` (8 file).
  - Xóa 2 bản thảo trùng lặp ở thư mục gốc: `AI powered Investment.md` và `SYSTEM_SPECIFICATION.md v1.0.md`.
- **Việt hóa toàn bộ README:**
  - `README.md` gốc repo được viết lại 100% bằng tiếng Việt.
  - Các file `configs/README.md`, `database/migrations/README.md`, `notebooks/README.md`, `offline_package/README.md`, `scripts/README.md` được dịch chuẩn hóa tiếng Việt.
- **Dọn sạch metadata trôi lệch:** Xóa bỏ hoàn toàn các ghi chú `Bản gốc tiếng Anh` và `Bản tiếng Anh là nguồn chính thức` khỏi header của các file tiếng Việt. Các tài liệu tiếng Việt nay là nguồn chân lý duy nhất.
- **Sửa số liệu API sai:** `docs/api.html`, `docs/index.html`, `docs/modules.html`, `docs/status.html`, `docs/API_SPECIFICATION_vi.md`, `helper/resources_vi.md`, `memory-bank/current-state_vi.md` đều ghi "38 đường dẫn / 39 thao tác". Kiểm chứng lại bằng `app.openapi()`: **39 đường dẫn / 40 thao tác** trên `/api/v1/*` (41/42 nếu tính `/healthz` + `/readyz`).
- **Bổ sung hàng KI-012 còn thiếu** vào `memory-bank/known-issues_vi.md` và cập nhật các sự cố liên quan.
- **Làm rõ tình trạng T014:** Mã nguồn XONG, huấn luyện trên dữ liệu thật chờ KI-012 với lối mở là cờ `--source {memory,db}`.


## 2026-09-26 — D4: làm mới hướng dẫn triển khai cho bước 3

- `docs/DEPLOYMENT_vi.md`: đánh dấu "BẠN ĐANG Ở ĐÂY" tại bước 3, đánh số lại 11–21, thêm bước bắt buộc `docker compose build api worker` + kiểm tra log 3 job, chuỗi Yahoo ingest → `compute-scores` → đọc lại qua API, cập nhật lại trạng thái roadmap production (KI-008 phần đọc XONG, KI-009 chờ chính việc nạp dữ liệu của bạn, lệch DSN của worker là mục 7), thêm các hàng troubleshooting mới.
- `helper/deployment.md` + `docs/DEPLOYMENT.md`: bảng biến môi trường (`MARKET_DATA_SOURCE`, `SCHEDULER_*`), mục scheduler/job, lệnh test `LLM_PROVIDER=mock` (422 passed, 3 skipped).

## 2026-09-25 — D3: dời site tài liệu tĩnh + làm mới theo dữ liệu thật + nối biến môi trường (xong)

- `docs/htmldocs/*.html` + `style.css` dời sang `docs/` (đổi tên bằng `git mv`, giữ lịch sử); liên kết `style.css` vẫn tương đối (`href="style.css"`), các trang liên kết chéo bằng href tương đối phẳng.
- `status.html` làm mới: hàng E2E trực tiếp (`ingest --source yahoo FPT,VCB,HPG,ACB` → fetched=62 written=62 quality=94.88; `compute-scores` → scored=4; 422 passed/3 skipped), mục mới "Cấu hình mới qua biến môi trường" (`MARKET_DATA_SOURCE`, `SCHEDULER_*`, RAG, cổng chất lượng, cấu hình nguồn), trạng thái một phần của KI-006/KI-008/KI-010/KI-011; sửa văn bản lẫn tiếng Romania trong `modules.html` (`rag_doc_rows`).
- `.env.example` + `docker-compose.yml`: thêm `MARKET_DATA_SOURCE` (compose `:-auto`, code mặc định vẫn `memory`) và toàn bộ 10 biến `SCHEDULER_*`; tên đã được kiểm chứng với `Settings` trong `apps/api/config.py` (ánh xạ prefix `SCHEDULER_` của pydantic-settings; đã xác nhận việc tiêu thụ ở compose/worker; container vẫn cần `docker compose build api worker` + tạo lại để nhận).
- `helper/resources.md`: bảng biến môi trường + hàng CaféF + mục API + tham chiếu CLI (nạp yahoo, `compute-scores`, scheduler) cập nhật theo hiện trạng 2026-09-25.
- Kiểm chứng: `LLM_PROVIDER=mock pytest` → **422 passed, 3 skipped**; `ruff check .` sạch; `mypy` sạch (126 tệp); cả 7 trang HTML cân bằng thẻ; kiểm tra liên kết nội bộ OK.
- Phát hiện đổi tên giữ lịch sử cho 7/8 trang (`git mv`); `status.html` bị viết lại nhiều nên được ghi nhận là xoá+thêm (`git log --follow` vẫn lần được).

## 2026-09-18 (2) — Phase 2 được mở khoá từ host (lệch `POSTGRES_PASSWORD`)

- `.env` khôi phục về `POSTGRES_PASSWORD=change_me` + `DATABASE_URL` khớp (giá trị mà volume CSDL được khởi tạo ngày 2026-09-13); tạo lại ngăn xếp để api/worker nhận DSN mới. `POSTGRES_PASSWORD` chỉ được đọc ở lần khởi tạo đầu, nên chỉ sửa `.env` không bao giờ đổi được role sẵn có — đã ghi vào `docs/DEPLOYMENT_vi.md` + `helper/deployment_vi.md`.
- Kiểm chứng phase-2 phía host đạt: `alembic current` → `0001_initial_schema (head)`, `alembic upgrade head` exit 0, `python -m database.seeds.run_all` → 3 exchanges / 10 sectors / 15 industries / 30 dòng VN30 (idempotent), số đếm `39 | 12 | 30`.
- Chặn còn lại: firewall/forwarding của host vẫn chặn gói container→`db`/`qdrant` (`alembic heads` chạy được trong container, `alembic current` timeout, exit 143).

## 2026-09-18 — Triển khai: thiếu cấu hình Alembic trong image (+ chặn ở host/env)

- **Đã sửa (repo):** `alembic upgrade head` trong container lỗi `FAILED: No 'script_location' key found in configuration`. `alembic.ini` (gốc repo, `script_location = database/migrations`) chưa bao giờ được copy vào image và Compose chỉ mount `./src` + `./database`. `docker/Dockerfile.api` và `Dockerfile.worker` nay `COPY ... alembic.ini ./`; image dashboard vẫn tối giản (không `database/`, không migration). Đã kiểm chứng trong container: `alembic heads` → `0001_initial_schema (head)`.
- **Kiểm thử:** `tests/unit/test_deployment_config.py` mới bảo vệ bất biến này (script_location phân giải được, ini không chứa chứng thực thật + `env.py` ưu tiên `DATABASE_URL`, image có migration thì cũng có config, image chạy được alembic, alembic vẫn là phụ thuộc lõi).
- **Tài liệu:** thêm mục troubleshooting cho `script_location`, `password authentication failed` (lệch chứng thực) và "container không tới được db/qdrant" trong `docs/DEPLOYMENT_vi.md` + `helper/deployment_vi.md`.
- **Báo cáo (không phải lỗi repo):** (1) firewall/forwarding của host chặn gói container→container tới `db`/`qdrant` — chứng minh bằng bộ đếm veth (host→container và container→api/worker/dashboard vẫn chạy); cần kiểm tra iptables/nft với quyền root hoặc khởi động lại Docker. (2) `POSTGRES_PASSWORD` trong `.env` không còn khớp role trong volume khởi tạo 2026-09-13 (`change_me` vẫn xác thực được).


## 2026-09-17 — Kiểm toán mã: sửa lỗi logic/nhất quán trên data, quant, backtest, ML, RAG, agents, API

- Kiểm toán toàn bộ mã nguồn (`src/`, `apps/`, `configs/`); 16 khiếm khuyết được tìm và sửa:
  - **Engine backtest** (`src/backtesting/engine.py`): bán một phần ghi nhận TOÀN BỘ nhánh đang mở (P&L phồng ~2×, phần còn lại bị mồ côi) → nay chỉ ghi số lượng đã bán và giữ phần còn lại mở (giữ giá/ngày vào gốc); thêm vào thì gộp vào nhánh mở theo VWAP (bình quân giá). Trọng số mục tiêu tổng > 1.0 nay ném lỗi (không margin ngầm). Thứ tự khớp **bán trước mua**. Thêm dải không giao dịch 0.5% (`MIN_REBALANCE_PCT`). Điểm vốn cuối được đánh dấu lại sau thanh lý cuối cửa sổ (đã tính chi phí trong `final_equity()`).
  - **Chỉ số backtest** (`metrics.py`): `transaction_cost_total`/`turnover` chỉ đếm nhánh vào; engine nay báo chi phí/notional đã trừ chính xác qua override trong `compute_metrics` (ước lượng từ trade log vẫn là fallback cho người gọi hàm thuần).
  - **Phân rã điểm** (`src/quant/scoring/engine.py`): đóng góp dùng trọng số nền THÔ trong khi điểm tổng đã chuẩn hoá lại — tỉ trọng không cộng thành 1 khi thiếu hệ số. Nay mọi đóng góp dùng trọng số đã chuẩn hoá (Σ weighted == overall, Σ share == 1). `configs/scoring_weights.yaml` được chốt chặn trôi bằng unit test.
  - **Kho RAG** (`src/rag/retrieval/store.py`): point id cho Qdrant dùng `hash()` (bị PYTHONHASHSEED ngẫu nhiên hoá → mirror không idempotent) → `stable_point_id` (dựa trên sha256); thêm `MemoryVectorStore.vectors_for()` công khai thay cho việc `RagService` truy cập thuộc tính riêng.
  - **Client dashboard** (`apps/dashboard/client.py`): gọi `/stocks/rankings` nhưng route API là `/stocks/ranked` → xếp hạng luôn rơi vào fallback trong tiến trình; đã sửa + xoá nhánh `_fallback` chết trùng lặp (`/stocks/{symbol}/indicators` bị che bởi khoá trùng).
  - **Auth** (`apps/api/routers/auth.py`): thông tin sai trả HTTP 200 kèm thân lỗi; nay ném 401 `invalid_credentials` và so sánh bằng `secrets.compare_digest`.
  - **Catalog tool** (`src/agents/tools.py`): `call()` cho phép mọi phương thức của lớp (kể cả helper riêng) — nay allowlist chính là `catalog` §22.
  - **Registry model** (`src/ml/model_registry.py` + `predictor.py` + `apps/worker/cli.py`): mỗi trainer/service dự đoán tự dựng registry riêng → model đã huấn luyện vô hình với tầng phục vụ. Đã thêm `get_default_registry()` dùng chung toàn tiến trình.
  - **Khử trùng tin trong pipeline** (`src/data/pipelines.py`): nạp TOÀN BỘ bảng `news` mỗi lần chạy; nay chỉ tra tiêu đề của lô hiện tại.
  - **CLI worker**: `ingest --dataset prices` thiếu `--symbols` từng "thành công" với lần chạy rỗng → nay thoát mã 2 kèm thông báo rõ; mốc thời gian tin fixture chuyển sang 15:00 (cửa sổ cùng ngày không còn lấy về 0 mục dưới điều kiện `published > since`).
  - **Singleton RagService**: `get_rag_service()` nay lấy giống từ `MarketService` DÙNG CHUNG (`get_market_service()`), không phải instance riêng; router monitoring dùng singleton.
  - **Dataset đặc trưng** (`src/ml/feature_dataset.py`): `FEATURE_VERSION`/`DEFAULT_HORIZON_DAYS` bị định nghĩa hai lần; nay chỉ định nghĩa một lần ở đầu module.
- Test: +17 unit test (bán một phần, chốt tổng trọng số, chi phí/turnover hai nhánh, đồng nhất chi phí engine-vs-metrics, đóng góp chuẩn hoá lại, point id ổn định qua PYTHONHASHSEED, hiển thị tin fixture, từ chối tool riêng, auth 401, cờ algorithm, đồng bộ trọng số-vs-yaml). **342 passed, 1 skipped** · `ruff check .` sạch · mypy sạch (119 tệp).
- Tài liệu cập nhật: `docs/BACKTESTING.md` §6 (quy tắc khớp), `docs/QUANT_ENGINE.md` §7 (hợp đồng phân rã), `docs/API_SPECIFICATION.md` §3 (ngữ nghĩa 401), `helper/resources_vi.md` (tham chiếu CLI); trang HTML `index.html`/`status.html`/`modules.html` (số test 301→342, quy tắc khớp backtest, hàng kiểm toán); memory bank (tệp này, `current-state.md`, `known-issues.md`, `tasks.md`).


## 2026-09-16 — T014: dự đoán ML (dataset đặc trưng + huấn luyện + hiệu chuẩn + registry + API)

- Hoàn thành `src/ml/` (T014):
  - `feature_dataset.py` — `FeatureDatasetBuilder` với canh chỉnh as-of nghiêm ngặt; **loại bỏ rò rỉ mục tiêu** (các cột lợi nhuận tương lai `horizon_return_*` từng bị ghi vào ma trận đặc trưng — `horizon_return_5d` bằng đúng mục tiêu huấn luyện); mã hoá mã cổ phiếu bằng `zlib.crc32` ổn định theo tiến trình (trước là `hash()`, bị PYTHONHASHSEED ngẫu nhiên hoá); Protocol `MarketLike` định kiểu theo `MarketService`
  - `training.py` — `ModelTrainer`: chia theo thời gian 60/20/20 trên **ngày giao dịch duy nhất** (chia theo số dòng có thể đặt một ngày vào hai phần), fit XGBoost, **`_SigmoidCalibrator` tự viết** (thay `CalibratedClassifierCV cv="prefit"` đã bị xoá ở scikit-learn 1.8), chỉ số phân loại (AUC/Brier/log-loss/accuracy/precision/recall/F1), kiểm chứng đầu vào (canh dòng, nhãn 0/1, ≥3 ngày) và **chốt chặn phần chỉ có một lớp** — `train_and_register()` → bản ghi APPROVED
  - `model_registry.py` / `predictor.py` — vòng đời EXPERIMENTAL→…→DEPRECATED + dịch vụ dự đoán có stub dự phòng tất định
- Thêm `apps/api/routers/predictions.py` — 3 endpoint: `GET /api/v1/predictions/{symbol}`, `/predictions/{symbol}/evaluations`, `/predictions/{symbol}/validation` (đặc tả §2.8) → API **39 đường dẫn / 40 thao tác**
- Thêm lệnh `train-model` vào `apps/worker/cli.py` (+ refactor `build_parser()`); trên fixture tổng hợp nó báo lỗi to (nhãn một lớp) thay vì đăng ký model giả
- Thêm test: `test_ml_no_leakage.py` (5: không có cột lợi nhuận tương lai, bất biến với cú sốc tương lai, mục tiêu phản ứng với giá tương lai, ổn định theo PYTHONHASHSEED), `test_ml_training.py` (7: fit/hiệu chuẩn thật, kích thước phần theo ngày, từ chối một lớp theo phần, kiểm chứng mục tiêu/nhãn/canh dòng), +5 test API dự đoán +2 test CLI trong `test_t014_t015.py`
- Thêm **KI-012**: fixture tổng hợp tăng đơn điệu → 100% nhãn 5 ngày dương; không thể huấn luyện classifier thật cho tới khi có dữ liệu thật (bị chặn bởi KI-006/007/008); trong lúc đó predictor phục vụ fallback tất định
- Cập nhật `docs/status.html` (ML 80% · hàng T014 · KI-012 · roadmap → T015); memory bank (active-task/current-state/tasks)
- Kiểm chứng: **325 test pass** · `ruff check .` sạch · `mypy` → "Success: no issues found in 119 source files"

## 2026-09-15 — T012: nạp tin + RAG + engine bằng chứng (Giai đoạn 4 → MVP-2)

- Thêm `src/rag/` (T012):
  - `embedding/hash_embed.py` — `HashEmbedding`: embedding băm tất định (dim 128, `model_name="hash-embed-v1"`), không phụ thuộc model ngoài; `embed(text) -> list[float]`
  - `ingestion/chunking.py` — dataclass `Chunk` + `chunk_news_item(item, max_chars=800)`: chia cửa sổ trượt kèm metadata (symbol, doc_type="news", source, published_at, title)
  - `retrieval/store.py` — `MemoryVectorStore` (cosine trong bộ nhớ, `upsert`/`query`/`size`) + `QdrantAdapter` (mirror best-effort, chỉ khi import được `qdrant_client`)
  - `retrieval/retriever.py` — `RankedDoc` + `Retriever.retrieve(...)`: hybrid vector + trùng từ khoá + độ mới + tiên nghiệm độ tin cậy nguồn, lọc metadata (symbol/doc_type/source)
  - `reranking/reranker.py` — `rerank(query, docs)`: chấm lại kiểu RRF kết hợp hạng vector/từ khoá/độ mới
  - `service.py` — `RagService`: singleton `ingest_news_items`/`search`/`evidence_for`/`status`/`to_payload`/`evidence_payload`
- Thêm `src/evidence/engine.py` — dataclass `Evidence` (§19) + `confidence_for(doc)` + `build_evidence(...)` + `evidence_to_dict(ev)`; provenance chi tiết (chunk id, mã, nguồn, published_at, snippet)
- Thêm phần nối API:
  - `apps/api/routers/rag.py` — 3 endpoint: `GET /api/v1/rag/search`, `GET /api/v1/rag/status`, `GET /api/v1/evidence` → API tổng **26 đường dẫn / 27 thao tác** (trước là 23/24)
  - `apps/api/services/rag_service.py` — singleton `get_rag_service()` toàn tiến trình, khởi tạo lazy từ fixture `MarketService().list_news()` (KI-011)
  - `apps/api/main.py` — đăng ký router `rag`; `readyz` nay báo trạng thái `qdrant` (`offline-index-ready` khi không có client)
- Thêm `tests/unit/test_rag_evidence.py` (20 test: chia chunk, ổn định/tất định của embedding, upsert/query kho, lọc truy xuất hybrid, đơn điệu của rerank, khoảng tin cậy bằng chứng, lược đồ dict bằng chứng) + 3 test API mới trong `tests/unit/test_api.py`
- Thêm KI-011 (chỉ mục RAG trên tin tổng hợp; Qdrant adapter best-effort; tin thật bị chặn bởi KI-006/KI-007 — *nay đã có 50 bài CaféF thật, 2026-09-24/25*)

- Cập nhật `docs/htmldocs/` (quy tắc thường trực): `status.html` thanh RAG 0→85% + hàng T012 + roadmap (T013 kế tiếp) + hàng KI-011; `index.html` hàng RAG + huy hiệu 232 test; `modules.html` mục RAG T012 + anchor TOC; `api.html` endpoint rag/evidence + số 26/27; `structure.html` đánh dấu rag/evidence xong
- Kiểm chứng: **232 test pass** · `ruff check .` sạch · `mypy src/ apps/` → "Success: no issues found in 102 source files"

## 2026-09-15 — T011: dashboard Streamlit

- Thêm `apps/dashboard/` (T011):
  - `client.py` — `MarketClient`: HTTP-first qua `/api/v1/*`, fallback `MarketService` trong tiến trình khi ngoại tuyến; phương thức cho indices/regime/breadth, stocks/ranked/prices/ranking, indicators, valuation, quality, news, backtests/backtest/metrics/trades, health; biến `API_HOST` ghi đè mặc định
  - `components.py` — định dạng/biến đổi độc lập framework: `signal_label/signal_color`, `format_price/format_percent/format_date`, `ranking_rows/contribution_rows/price_dataframe/indicator_dict/quality_bar_labels/metric_rows/news_rows`
  - `app.py` — 6 trang Streamlit: tổng quan thị trường, bộ lọc, xếp hạng, chi tiết mã, backtests, sức khỏe hệ thống (biểu đồ plotly nến/scatter/đóng góp)
- Thêm `tests/unit/test_dashboard.py` (34 test); thêm `plotly` vào phụ thuộc `pyproject.toml` + override mypy cho thư viện UI
- Thêm KI-010 (dashboard phục vụ dữ liệu tổng hợp trong bộ nhớ cho tới khi TimescaleDB + dữ liệu thật được nối)
- Cập nhật `docs/htmldocs/`: hàng dashboard DONE trong `status.html` + bảng task hoàn thành + bảng KI, hàng dashboard trong mục nền tảng `index.html`, mục dashboard T011 + anchor TOC trong `modules.html`
- Kiểm chứng: **209 test pass** · `ruff check .` sạch · `mypy src/ apps/` → "Success: no issues found in 93 source files"

## 2026-09-15 — T008/T009/T010: khả năng giải thích, backtesting, tầng API

- Thêm `src/quant/scoring/engine.py` (T008):
  - `decompose_score(factor_scores, weights=None)` — đóng góp theo hệ số với trọng số chuẩn hoá lại (xử lý thiếu/bằng 0)
  - `score_universe(universe_scores, weights=None)` → danh sách `StockRanking` đã xếp hạng
  - `build_signal_label(score)` → POSITIVE/NEUTRAL/NEGATIVE (§44)
  - `build_confidence(overall, n_factors)` — độ tin cậy giảm khi thiếu hệ số
  - Dataclass: `FactorContribution`, `ScoreDecomposition`, `StockRanking`
  - Thêm `tests/unit/test_scoring_engine.py` (11 test)
- Thêm `src/backtesting/` (T009):
  - `models.py` — `PriceBar`, `BacktestData`, `ExecutionCosts`, `Trade`, `EquityPoint`, `BacktestConfig`, `BacktestResult`
  - `metrics.py` — 11 chỉ số: `total_return`, `cagr`, `annualized_volatility`, `sharpe_ratio`, `sortino_ratio`, `max_drawdown`, `calmar_ratio`, `win_rate`, `profit_factor`, `turnover`, `transaction_cost_total`, + `compute_metrics`
  - `engine.py` — `run_backtest` (khớp giá mở nến kế tiếp, tính chi phí), `select_window`
  - `walkforward.py` — `walk_forward_windows`, `rolling_windows`, `WalkForwardWindow`
  - Thêm `tests/unit/test_backtesting.py` (10 test)
- Thêm `apps/api/` (T010):
  - `main.py` — ứng dụng FastAPI, `/healthz`, `/readyz`
  - 7 router: `market`, `stocks`, `fundamentals`, `technical`, `valuation`, `news`, `backtests` = 23 đường dẫn / 24 thao tác
  - `schemas.py` (21 model Pydantic gồm `Page[T]` generic, `ErrorResponse`)
  - `dependencies.py` (`MarketDep`), `services/market_data.py` (service tất định trong bộ nhớ — KI-008)
  - `routers/common.py` — `paginate_params`, `page_of`, phong bì `not_found`
  - Thêm `tests/unit/test_api.py` (14 test)
  - Ghi mục module T008/T009/T010 mới vào `docs/htmldocs/modules.html`
  - Tạo `docs/htmldocs/api.html` — trang tham chiếu cho REST API
  - Cập nhật `docs/htmldocs/status.html` và `structure.html`
- Kiểm chứng: **175 test pass** · `ruff check .` sạch · `mypy src/ apps/` → "Success: no issues found in 91 source files"
- Thêm `KI-008` (API dùng service tổng hợp trong bộ nhớ, chưa nối TimescaleDB) và `KI-009` (backtest chỉ kiểm chứng trên dữ liệu tổng hợp) vào `known-issues.md`

- Quy tắc thường trực mới (ghi trong `tasks.md` + `decisions.md`): mọi task tương lai
  thay đổi mã nguồn, lược đồ, cấu hình hoặc hành vi BẮT BUỘC cũng phải cập nhật
  tài liệu HTML tiếng Việt trong cùng task — trang trạng thái, tham chiếu module và mọi
  trang bị ảnh hưởng — và kiểm chứng lại HTML trước khi đánh dấu hoàn thành.
  Ngăn tài liệu trôi lệch khi dự án tiến hoá.


## 2026-09-14 — T007 Quant Engine: hệ số/định giá/động lượng/rủi ro + chấm điểm (Giai đoạn 2)

- Thêm `src/market/fundamental/factors.py` — tăng trưởng doanh thu/EPS, ROE, ROA, biên gộp/hđkd/ròng, D/E, khả năng trả lãi, FCF, biên FCF, chất lượng lợi nhuận (`None` khi mẫu số bằng 0)
- Thêm `src/market/valuation/valuation.py` — P/E, forward P/E, P/B, EV/EBITDA, EV/Sales, tỉ suất cổ tức, PEG, enterprise value + hạng percentile/ngành/lịch sử
- Thêm `src/market/momentum/momentum.py` — lợi nhuận n ngày, lợi nhuận đa khung, mở rộng khối lượng, động lượng tương đối so với benchmark
- Thêm `src/market/risk/risk.py` — độ biến động niên hoá cuộn (log return, sqrt(252)), beta cuộn, max drawdown trượt, thanh khoản, rủi ro gap, nhóm rủi ro nợ
- Thêm `src/quant/factors/scoring.py` — trọng số nền §12, điểm hệ số theo hạng percentile, điểm tổng chuẩn hoá lại, xếp hạng cổ phiếu
- Sửa lỗi lint/kiểu: dòng trống cuối tệp, `zip(strict=True)`, tách dòng dài, lỗi typo `universe_values: dict[str, list[float]]`
- Thêm `tests/unit/test_quant_factors.py` + `test_quant_scoring.py` (18 test)
- Kiểm chứng: ruff sạch, mypy sạch (5 tệp nguồn), **140 test pass**
- Cập nhật `tasks.md` (T007 xong, T008 kế tiếp), `current-state.md` (Quant 90%), `decisions.md`

## 2026-09-14 — T006 Quant Engine: chỉ báo kỹ thuật (Giai đoạn 2)

- Thêm `src/market/technical/indicators.py` — cài đặt thuần Python tất định:
  - `sma(close, period)` — trung bình động đơn giản
  - `ema(close, period)` — trung bình động hàm mũ (khởi tạo bằng SMA, hệ số chuẩn)
  - `rsi(close, period=14)` — chỉ số sức mạnh tương đối (làm trơn Wilder)
  - `macd(close, fast=12, slow=26, signal=9)` — đường MACD, signal, histogram
  - `bollinger_bands(close, period=20, num_std=2)` — biên trên, giữa (SMA), dưới
  - `atr(high, low, close, period=14)` — Average True Range (làm trơn Wilder)
  - `obv(close, volume)` — On-Balance Volume
  - `volume_sma(volume, period=20)` — SMA khối lượng
  - `relative_strength(close, benchmark_close)` — tỉ lệ so với benchmark
- Thêm `tests/unit/test_technical_indicators.py` (40 test) — test giá trị kỳ vọng cho mỗi chỉ báo
- Thêm `[tool.mypy.overrides]` cho `tests.*` (nới nghiêm ngặt trên tệp test)
- **Kiểm chứng:** `ruff check` sạch · `mypy` sạch · `pytest` → **122 passed**

## 2026-09-13 — T002 thiết kế nguồn dữ liệu + kế hoạch chứng thực (BƯỚC 4)

- Thêm `docs/DATA_SOURCES.md`: chọn provider theo miền (thị trường, cơ bản, định giá, vĩ mô, sự kiện doanh nghiệp, tin tức) kèm chuỗi chính + dự phòng, quyết định định giá-do-engine-tính, kế hoạch chứng thực và danh sách `TO VERIFY` cho T004.
- Thêm `configs/sources.yaml` — registry provider máy đọc được (id, vai trò, auth, *tên* biến chứng thực, enabled/priority, chọn theo miền + chuỗi dự phòng).
- Mở rộng `.env.example` với bộ chọn provider (mặc định `ssix_finipro`/`cafef`) và chỉ **tên** biến chứng thực (`FINIPRO_ACCESS_TOKEN`, `VIETSTOCK_API_KEY`, `TRADINGECONOMICS_API_KEY`) — không commit secret.
- Thêm `tests/unit/test_sources_registry.py` (7 test) kiểm chứng cấu trúc registry, tính nhất quán chọn/dự phòng và chính sách không chứa secret.
- Cập nhật `configs/README.md`, `helper/resources.md`, `README.md`, `project-context.md`.
- **Trung thực kiểm chứng:** không có egress mạng ⇒ không xác nhận được endpoint/lược đồ provider, đánh dấu `TO VERIFY` cho T004 (KI-006). `PyYAML` chỉ được cài vào venv cục bộ để thực sự chạy (không bỏ qua) test registry; `pyproject.toml` không đổi — thêm nó làm phụ thuộc dev cần được duyệt.


## 2026-09-13 — BƯỚC 2 THIẾT KẾ CSDL đã triển khai (T003)

- Thêm model SQLAlchemy (`src/common/models/`) bao mọi bảng trong `docs/DATABASE_SCHEMA.md` — 38 bảng, `Base` dùng chung + quy ước đặt tên + mixin `Timestamp`/`Audit`.
- Thêm migration Alembic đầu tiên `database/migrations/versions/0001_initial_schema.py` (tạo mọi bảng từ metadata model + chuyển 12 bảng chuỗi thời gian thành TimescaleDB hypertable theo §17).
- Nối `Base.metadata` vào `database/migrations/env.py` (`target_metadata`).
- Thêm seed idempotent (`database/seeds/`): exchanges (HOSE/HNX/UPCOM), 10 sector + 15 industry, universe VN30 30 dòng; nối vào `database/seeds/run_all.py`.
- Thêm unit test `tests/unit/test_models.py` (hợp đồng metadata, hợp đồng hypertable của migration, toàn vẹn dữ liệu seed); cập nhật test seed trong `test_smoke.py` để không cần CSDL.
- **Quyết định:** `predictions` giữ là bảng thường (quy tắc unique-index của Timescale so với FK của `prediction_evaluations`); PK `signals` tổ hợp `(id, trade_date)`; VN30 seed như danh sách nền.
- **Đã kiểm chứng:** `alembic upgrade head` → `downgrade base` → `upgrade head` đều thành công trên TimescaleDB Docker đang chạy (38 bảng, 12 hypertable); seed chèn đúng và idempotent; `ruff` sạch; `pytest` 11 passed; `mypy` sạch trên `src/common/models` + `database/seeds`.

## 2026-09-06 — Hoàn thành Phase 0 (+ kiểm chứng)

- Khởi tạo kho git (`/home/dvtung/Projects/DTCK`).
- Dựng khung bố cục repo theo đặc tả §35.
- Di chuyển/sao chép tệp đặc tả vào `docs/`:
  - `docs/SYSTEM_SPECIFICATION.md` (chuẩn, v1.0, 58 mục)
  - `docs/AI_INVESTMENT_CONCEPT.md` (bản nháp ý tưởng trước đó)
- Soạn bộ tài liệu (13 tệp): ARCHITECTURE, DATABASE_SCHEMA, DATA_ARCHITECTURE, QUANT_ENGINE, BACKTESTING, ML_ARCHITECTURE, RAG_ARCHITECTURE, AGENT_ARCHITECTURE, API_SPECIFICATION, DEPLOYMENT, SECURITY + hai tệp đặc tả.
- Khởi tạo memory bank: project-context, current-state, decisions, architecture-decisions, known-issues, tasks, changelog.
- Tạo: `pyproject.toml`, `.env.example`, `.gitignore`, `README.md`, `requirements.txt`, `docker-compose.yml`, `docker/Dockerfile.api`, `docker/Dockerfile.worker`, `docker/Dockerfile.dashboard`.
- Thêm entry point ứng dụng: `apps/api/main.py` (+`config.py`), `apps/worker/main.py` (+`cli.py`), `apps/dashboard/app.py`.
- Thêm khung Alembic (`alembic.ini`, `database/migrations/env.py`, `script.py.mako`) và `database/seeds/run_all.py`.
- Thêm `__init__.py` giữ chỗ gói (49 tệp) dưới `src/`, `apps/`, `database/`, `tests/`.
- Thêm `helper/deployment.md` và `helper/resources.md` (hướng dẫn vận hành theo quy tắc kỹ thuật), `offline_package/` (README + requirements-offline.txt), `configs/scoring_weights.yaml`, `scripts/README.md`, `notebooks/README.md`.
- Thêm smoke test `tests/unit/test_smoke.py`.
- **Đã kiểm chứng:** `docker compose config` OK · `pyproject.toml` parse được · `python -m py_compile` OK · `ruff check` sạch · `pytest` → **4 passed** (venv cục bộ `.venv`, Python 3.14).
- Chưa viết mã ứng dụng (theo thiết kế — Giai đoạn 1 là nền tảng dữ liệu).

