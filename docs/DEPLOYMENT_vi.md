# Hướng dẫn triển khai DTCK (Tiếng Việt)

> Phiên bản: 2026-09-26 · nhánh `feat/data-source-design` · commit `7b048c5`
> Trạng thái: **bạn đang ở bước 3** — kiểm tra API/DB trong container + nạp dữ liệu thật.

Dựa trên cấu hình thực tế của repo (docker-compose, Alembic, seeds, các KI đã biết).

---

## Giai đoạn 0: Chuẩn bị môi trường

**Yêu cầu:** Docker Engine 24+, Docker Compose v2, Git. (Local Python 3.12–3.14 nếu chạy ngoài Docker.)

```bash
# 1. Clone dự án
git clone https://github.com/dvtung/DTCK.git
cd DTCK

# 2. Tạo file môi trường từ mẫu (KHÔNG commit .env)
cp .env.example .env
```

**3. Điền biến môi trường trong `.env`:**

| Nhóm biến | Bắt buộc? | Ghi chú |
|---|---|---|
| `POSTGRES_USER/PASSWORD/DB`, `DATABASE_URL` | ✅ | Đổi `change_me` thành mật khẩu thật. ⚠️ **Lệch DSN trong compose:** `api` dùng `…:${POSTGRES_PASSWORD:-change_me}@…`, còn `worker` đang ghi cứng `…:${POSTGRES_PASSWORD:-dtckpassword}@…` — nếu `.env` không đặt `POSTGRES_PASSWORD` thì worker sai mật khẩu. Cách an toàn: đặt `POSTGRES_PASSWORD` rõ trong `.env` (cả hai service cùng đọc một giá trị) |
| `QDRANT_URL` | ✅ | Mặc định `http://localhost:6333` |
| `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL`, `LLM_TIMEOUT_SECONDS`, `LLM_THINK` | Tùy (T016) | `mock` để chạy offline không tốn phí (test không gọi mạng). Đã nối tầng suy luận: `local` + `LLM_MODEL=qwen3.5` + `LLM_BASE_URL=http://host.docker.internal:11434` ⇒ Ollama máy host trả `thesis` tiếng Việt cho Analysis Agent (chi tiết `docs/AGENT_ARCHITECTURE_vi.md` §8.1). `LLM_THINK=false` (mặc định) tắt khối suy luận của model hybrid để giữ độ trễ trong hạn mức §45. Chạy test với `LLM_PROVIDER=mock MARKET_DATA_SOURCE=memory` |
| `MARKET_DATA_SOURCE` | ✅ (mới) | Chế độ đọc của API: `memory` (mặc định trong code — không cần DB) · `db` (ép đọc TimescaleDB) · `auto` (đọc DB khi bảng `prices` đã có dòng, ngược lại về memory). Compose đã đặt mặc định `auto` cho `api`/`worker` — cần **build lại image** mới có hiệu lực (xem Giai đoạn 3) |
| `SCHEDULER_*` (10 biến) | Tùy (mới) | Job worker lập lịch: `SCHEDULER_JOBS_ENABLED` (true/false) · tin tức `SCHEDULER_NEWS_SOURCE=cafef` mỗi `SCHEDULER_NEWS_INTERVAL_MINUTES=15` phút · EOD `SCHEDULER_EOD_SOURCE=ssix_finipro` lúc `SCHEDULER_EOD_CRON_HOUR:MINUTE=15:05` T2–T6 (nguồn chính SSI, tự chuyển `yahoo → vndirect → tcbs → dsc` khi lỗi/0 dòng), cửa sổ nạp lại `SCHEDULER_EOD_LOOKBACK_DAYS=7` · chấm điểm `SCHEDULER_SCORING_CRON_HOUR:MINUTE=15:30` T2–T6 (múi giờ `Asia/Ho_Chi_Minh`) |
| `DATA_QUALITY_THRESHOLD` | Tùy | Cổng chất lượng §39, thang 0–100 (mặc định `80.0`) |
| `NEWS_PROVIDER`, `NEWS_API_KEY` | Cho tin tức thật | ✅ CaféF RSS đã kiểm chứng 2026-09-25 (`cafef`, anonymous, 50 bài đã nạp thử) |
| `MARKET_DATA_PROVIDER`, `FINIPRO_ACCESS_TOKEN` | Cho dữ liệu thật | ✅ Yahoo EOD đã kiểm chứng 2026-09-25 (anonymous); FiniPro/VNDirect/TCBS vẫn chờ mạng/token (KI-006/007) |

```bash
# 4. Kiểm tra cấu hình compose trước khi chạy
docker compose config --quiet && echo "OK"
```

---

## Giai đoạn 1: Khởi động hạ tầng

```bash
# 5. Build + chạy toàn bộ stack (api, worker, dashboard, timescaledb, qdrant)
docker compose up --build -d

# 6. Chờ healthy (api/worker phụ thuộc healthcheck của db)
docker compose ps          # đợi STATUS = healthy/running
docker compose logs -f db  # đợi "database system is ready to accept connections"
```

**Thứ tự phụ thuộc:** `timescaledb` → `qdrant` → `api` + `worker` + `dashboard`. Nếu port conflict, đổi trong `.env` (`POSTGRES_PORT`, `API_PORT=8000`, `DASHBOARD_PORT=8501`).

### Nếu API lỗi `ModuleNotFoundError: No module named 'sklearn'`

`sklearn` thuộc package **scikit-learn**, nằm trong extra `[ml]` của dự án.
Dockerfile API/worker đã chuyển sang cài `.[dev,ml]`; package ML dùng lazy import
để API không kéo training stack ngay khi khởi động.

Phải **build lại image và tạo lại container**, chỉ `restart` không cài dependency mới:

```bash
docker compose build api worker
docker compose up -d --no-deps api worker
docker compose exec -T api python -c "import sklearn, xgboost, lightgbm; print(sklearn.__version__)"
docker compose exec -T worker python -c "from src.ml import ModelTrainer; print('OK')"
docker compose exec -T api curl --fail http://localhost:8000/healthz
```

Không cần xóa volume hay chạy lại migration. Image lớn hơn vì chứa thư viện ML;
không cần đổi Python 3.12 hay thêm biến môi trường.


---

## Giai đoạn 2: Database migration + seed

```bash
# 7. Chạy migration (38 bảng + 12 hypertable TimescaleDB)
docker compose exec api alembic upgrade head

# 8. Kiểm tra migration đã áp dụng
docker compose exec api alembic current     # phải hiện "0001 (head)"

# 9. Nạp dữ liệu tham chiếu (sàn HOSE/HNX/UPCOM, 10 ngành,
#    15 ngành chi tiết, VN30 30 mã) — idempotent, chạy lại được
docker compose exec api python -m database.seeds.run_all

# 10. Xác minh
docker compose exec db psql -U dtck -d dtck -c "\dt"        # 38 bảng
docker compose exec db psql -U dtck -d dtck -c \
  "SELECT count(*) FROM stocks;"                            # 30 (VN30)
```

> Rollback nếu cần: `docker compose exec api alembic downgrade base` (⚠️ mất dữ liệu).

---

## Giai đoạn 3: Kiểm tra dịch vụ + nạp dữ liệu thật ⬅️ **BẠN ĐANG Ở ĐÂY**

> Hoàn cảnh của bạn: Giai đoạn 1–2 đã xong (stack healthy,
> migration `0001 (head)`, seed VN30). Mục tiêu của bước này:
> (a) xác nhận container đang chạy **code mới nhất** (scheduler + DB read path),
> (b) kiểm tra API/dashboard/RAG, (c) nạp giá EOD thật qua Yahoo + chấm điểm.

### 3.0. Rebuild trước (bắt buộc — code mới sau lần build image cũ)

```bash
# 11. Build lại api + worker (scheduler 3 job, DbMarketService, SCHEDULER_*/MARKET_DATA_SOURCE)
docker compose build api worker
docker compose up -d --no-deps api worker

# 12. Xác nhận worker scheduler đã đăng ký đủ 3 job
docker compose logs worker 2>&1 | grep -i "registered job"
# kỳ vọng thấy: periodic_news_ingestion … daily_eod_ingestion … cron Mon-Fri 15:05 …
#               daily_eod_scoring … cron Mon-Fri 15:30 …
```

### 3.1. Kiểm tra API, dashboard, RAG trong container

```bash
# 13. API health + readyz
curl http://localhost:8000/healthz     # {"status":"ok",...}
curl http://localhost:8000/readyz      # dò THẬT từng phụ thuộc
# Kỳ vọng trên stack đã nạp dữ liệu (2026-09-27):
#   {"status":"ready",
#    "market_source":"auto->db",
#    "dependencies":{"database":"connected","qdrant":"up",
#                    "agents":"llm:qwen3.5"}}
# Ý nghĩa (không hardcode):
#   database  connected | connected-no-prices (CSDL thông nhưng `prices` rỗng) | unreachable
#   qdrant    up | offline-index-ready (thiếu qdrant_client — index in-memory vẫn chạy, KI-011)
#   agents    llm:<model> (LLM_PROVIDER=local, T016) | offline:<danh sách task>
#   market_source  <MARKET_DATA_SOURCE>-><service đang phục vụ: db|memory>

# 14. API hoạt động với dữ liệu seed + memory (khi prices còn trống thì auto về memory — đúng)
curl "http://localhost:8000/api/v1/market/indices?limit=3"
curl "http://localhost:8000/api/v1/stocks/FPT/ranking"

# 15. Smoke test RAG (2 bài mẫu trong seed + 50 bài CaféF thật đã nạp 2026-09-24)
curl "http://localhost:8000/api/v1/rag/search?query=VNINDEX&top_k=3"

# Swagger UI tương tác → http://localhost:8000/docs
# Dashboard (có trang "Tin tức & RAG" mới) → http://localhost:8501
# Qdrant dashboard → http://localhost:6333/dashboard
```

### 3.2. Nạp giá EOD thật (SSI FastConnect → Yahoo dự phòng) + chấm điểm

```bash
# 16. Nạp giá thật — SSI FastConnect là nguồn CHÍNH (kiểm chứng 2026-09-27:
#     fetched=68 written=68 quality=93.74 cho FPT,VCB,HPG,ACB 2026-09-01..26).
#     Cần SSI_CONSUMER_ID + SSI_CONSUMER_SECRET trong .env (hoặc FINIPRO_ACCESS_TOKEN).
docker compose exec -T worker python -m apps.worker.cli ingest --dataset prices \
  --source ssix_finipro --symbols FPT,VCB,HPG,ACB --start 2026-09-01 --end 2026-09-26

# 16b. Chỉ số qua SSI (Market/DailyIndex — VERIFIED 2026-09-27: written=34)
docker compose exec -T worker python -m apps.worker.cli ingest --dataset index_prices \
  --source ssix_finipro --indexes VNINDEX,VN30 --start 2026-09-01 --end 2026-09-26

# 16c. Dự phòng Yahoo khi SSI lỗi/hết hạn ngạch (chuỗi thị trường chạy cùng lệnh)
docker compose exec -T worker python -m apps.worker.cli ingest --dataset prices \
  --source yahoo --symbols FPT,VCB,HPG,ACB --start 2026-09-01 --end 2026-09-26

# 17. Chấm điểm trên dữ liệu thật (ghi vào bảng factor_scores)
docker compose exec -T worker python -m apps.worker.cli compute-scores --lookback 60

# 18. Đọc kết quả qua API (chế độ auto → DbMarketService vì prices đã có dòng)
curl -s "http://localhost:8000/api/v1/stocks/FPT/ranking" | head -c 600; echo
```

**Sau khi nạp xong:** API ở chế độ `auto` sẽ tự chuyển từ memory sang đọc TimescaleDB.
Dashboard trang xếp hạng và "Tin tức & RAG" sẽ hiện dữ liệu thật mà không cần đổi code.

---

## Giai đoạn 4: Dữ liệu thị trường

Nguồn **chính** là SSI FastConnect (`ssix_finipro`, priority 100, `VERIFIED_2026-09-27`
với credential consumer live); chuỗi dự phòng lấy từ `configs/sources.yaml`:
`ssix_finipro → yahoo (85, VERIFIED_2026-09-25) → vndirect (80) → tcbs (75) → dsc (70)`.
Job EOD 15:05 tự đi hết chuỗi này (`market_provider_chain`): nguồn nào không dựng
được (thiếu credential) hoặc trả 0 dòng thì ghi log và chuyển nguồn kế tiếp.
Tin tức qua `cafef` RSS (`VERIFIED_2026-09-25`, đã nạp 50 bài thật 2026-09-24).

**Lựa chọn A — Offline/fixture (mặc định, không cần mạng):**

```bash
# Nạp giá EOD từ fixture (deterministic, phục vụ test/demo)
docker compose exec -T api python -m apps.worker.cli ingest \
    --dataset prices --source fixture \
    --start 2026-09-01 --end 2026-09-05 --symbols FPT,VCB,HPG
```

**Lựa chọn B — Provider thật (Yahoo/CaféF đã mở, còn lại chờ KI-006/007):**

```bash
# Nạp tin tức CaféF (lọc theo mã, ví dụ FPT)
docker compose exec -T worker python -m apps.worker.cli ingest --dataset news \
  --source cafef --symbols FPT
```

Quy trình ingest chuẩn qua cổng chất lượng:

1. Bắt giá EOD mới nhất của một mã qua chain chính (**SSI FastConnect** trước, Yahoo sau)
2. Dịch mã `.VN` chỉ cần cho Yahoo: `FPT.VN`, `VCB.VN`, `HPG.VN`, `ACB.VN` (SSI dùng mã gốc `FPT`, `VCB`, …)
3. Chạy lại ingest với `--source yahoo` khi SSI lỗi/hết hạn ngạch (job 15:05 tự làm việc này)
4. **Quality gate §39**: batch dưới 80 điểm sẽ bị flag `below_threshold` và command trả exit code 1 — đây là hành vi đúng, không phải lỗi

**Worker scheduler (2026-09-25, cập nhật 2026-09-27):** container `worker` (`python -m apps.worker.main`)
chạy APScheduler blocking với **3 job thật**: tin tức mỗi N phút (`cafef`),
EOD Mon–Fri 15:05 (`SCHEDULER_EOD_SOURCE=ssix_finipro` + chuỗi dự phòng
`yahoo → vndirect → tcbs → dsc`, cửa sổ nạp lại 7 ngày), chấm điểm Mon–Fri 15:30
— múi giờ `Asia/Ho_Chi_Minh`, fail-soft (provider lỗi chỉ ghi log).
Tắt job bằng `SCHEDULER_JOBS_ENABLED=false` (endpoint `/news/ingest` vẫn dùng được).
Image cũ chưa có code này → phải `docker compose build api worker` (xem 3.0).

**Đọc DB qua API (2026-09-25, KI-008 đã mở phần đọc):**
`MARKET_DATA_SOURCE=db|auto` nối toàn bộ đường đọc vào `DbMarketService`
(13 nhóm bảng thật); mặc định vẫn `memory`; `/readyz` báo `market_source`
dạng `<chế độ>-><service>` (ví dụ `auto->db`).
Chiều **ghi** qua API (ví dụ `POST /backtests` ghi vào DB, JWT/RBAC) chưa có.

**Huấn luyện mô hình ML (T014, KI-012 đã đóng 2026-09-27):**

```bash
# Mặc định --source memory: fixture tổng hợp chỉ tăng → trainer từ chối
# trung thực (100% nhãn 5 ngày dương) — hữu ích cho test offline.
docker compose exec -T api python -m apps.worker.cli train-model

# Huấn luyện thật trên dữ liệu TimescaleDB (nhãn hỗn hợp):
# đã kiểm chứng 2026-09-27 — 616 hàng, roc_auc=0.702, model APPROVED.
docker compose exec -T api python -m apps.worker.cli train-model --source db
```

**Bảo mật API & quan sát (T015, 2026-09-27):**

```bash
# Bật API-key auth: đặt API_AUTH_KEY trong .env rồi
# docker compose up -d --force-recreate api
# Sau đó mọi POST/PUT/PATCH/DELETE dưới /api/v1/ (trừ /auth/login) và
# GET /metrics cần header: Authorization: Bearer <key>

# Scraping metrics (Prometheus text format, thuần stdlib — không thêm dependency):
curl -s http://localhost:8000/metrics
# dtck_http_requests_total · dtck_http_request_duration_seconds (histogram)
# dtck_agent_runs_total · dtck_agent_duration_seconds
```


## Giai đoạn 5: Xác thực chất lượng triển khai

```bash
# 19. Chạy toàn bộ test suite (trên máy chủ — thư mục `tests/` không nằm trong image api)
LLM_PROVIDER=mock MARKET_DATA_SOURCE=memory pytest -q   # kỳ vọng: 432 passed, 3 skipped

# 20. Lint + type check (image API cài kèm dev deps)
docker compose exec -T api ruff check .
docker compose exec -T api mypy            # kỳ vọng: 126 files, no issues

# 21. Xem dashboard (http://localhost:8501) — có trang "Tin tức & RAG" mới
```

---

## Giai đoạn 6: Vận hành hằng ngày

```bash
docker compose logs -f api worker           # theo dõi log
docker compose restart api                  # restart một dịch vụ
docker compose down                         # dừng, GIỮ volumes
docker compose down -v                      # dừng + XÓA dữ liệu (⚠️ phá hủy!)
docker compose pull && docker compose up -d --build   # cập nhật code mới
```

**Backup định kỳ (nên cấu hình cron):**

```bash
docker compose exec db pg_dump -U dtck dtck | gzip > backup_$(date +%F).sql.gz
```

---

## Các việc còn thiếu để production thật (roadmap §57)

| # | Việc | Trạng thái (cập nhật 2026-09-26) |
|---|---|---|
| 1 | **T015** — JWT/RBAC thật (login hiện là demo token), rate limiting, audit, CI/CD | Chưa làm |
| 2 | **KI-008 (phần còn lại)** — mặc định vẫn `memory`; chiều **ghi** qua API (`POST /backtests` vào DB) chưa có; các bảng chỉ số/báo cáo tài chính chưa có job ghi → `auto` chưa an toàn làm mặc định | Phần đọc ✅ DONE 2026-09-25 |
| 3 | **KI-009** — backfill lịch sử nhiều năm qua Yahoo để backtest có ý nghĩa (hiện mới ~1 tháng) | Chờ bước 3.3 của bạn |
| 4 | ~~**KI-012**~~ **ĐÃ GIẢI (2026-09-27)** — `train-model --source db` huấn luyện trên CSDL (nhãn hỗn hợp): 616 hàng, `roc_auc=0.702`, model APPROVED | Backfill lâu dài còn phụ thuộc KI-009 |
| 5 | HTTPS/reverse proxy (nginx/traefik) + secrets manager | Chưa có trong compose |
| 6 | Backup DB định kỳ (cron + `pg_dump`) | Chưa cấu hình |
| 7 | **Lệch DSN worker** — `docker-compose.yml`: `worker.DATABASE_URL` dùng fallback `dtckpassword`, `api` dùng `change_me`. Đặt `POSTGRES_PASSWORD` rõ trong `.env` để hai service giống nhau | Sửa khi rảnh (không chặn bước 3 nếu `.env` đã có mật khẩu) |

---

## Troubleshooting nhanh

| Triệu chứng | Nguyên nhân / cách xử lý |
|---|---|
| Port đã được sử dụng | Đổi `POSTGRES_PORT` / `API_PORT` / `DASHBOARD_PORT` trong `.env` |
| `FAILED: No 'script_location' key found in configuration` | Image cũ không chứa `alembic.ini` (đã sửa: bake vào image API/worker). Build lại: `docker compose build api worker && docker compose up -d --no-deps api worker` |
| `FATAL: password authentication failed for user "dtck"` | `.env` đổi `POSTGRES_PASSWORD` **sau khi** volume DB được khởi tạo — Postgres chỉ đọc biến này ở lần init đầu tiên. Đồng bộ lại: `docker compose exec -T db psql -U dtck -d dtck -c "ALTER USER dtck WITH PASSWORD '<mật-khẩu-trong-.env>'"`, hoặc khôi phục mật khẩu cũ trong `.env`, hoặc `docker compose down -v` (⚠️ mất dữ liệu) |
| Container `api` timeout khi tới `db` (không phải lỗi xác thực) | Firewall/forwarding của **host** chặn traffic giữa container (không phải lỗi dự án). Kiểm tra: `sudo iptables -S FORWARD`, `sudo nft list ruleset \\| grep -i drop`, `sudo ebtables -L`; sau đó `sudo systemctl restart docker` |
| `alembic upgrade` lỗi kết nối | DB chưa healthy — đợi `pg_isready`, xem `docker compose logs db` |
| `readyz` báo qdrant `offline-index-ready` | Image thiếu `qdrant-client` — từ 2026-09-27 Dockerfile cài extra `[qdrant]`. Build lại `docker compose build api worker && docker compose up -d --no-deps api worker`; ngoài ra đây vẫn là trạng thái hợp lệ (RAG dùng index in-memory, KI-011) |
| `readyz` báo database `unreachable` | Sai `DATABASE_URL`/DB chưa healthy (`docker compose ps db`, `docker compose logs db`) |
| `readyz` báo database `connected-no-prices` | CSDL thông nhưng bảng `prices` rỗng → `auto` phục vụ memory; nạp giá rồi `/readyz` sẽ báo `auto->db` |
| Ingest `prices` trả `fetched=0 written=0` | Sai khoảng ngày (ví dụ `--start/--end` trùng ngày nghỉ) hoặc symbol/mã chỉ số không đúng; SSI dùng mã gốc (`FPT`), Yahoo cần `.VN` |
| Ingest trả exit 1 | Quality gate §39 từ chối batch kém chất lượng — xem log `validation issue` |
| `train-model` lỗi "single class" | KI-012 — fixture tổng hợp chỉ tăng; dùng `--source db` để huấn luyện trên dữ liệu thật (đã đóng 2026-09-27) |
