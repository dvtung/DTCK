# Hướng dẫn triển khai (helper) — Bản tiếng Việt

## Nền tảng Nghiên cứu & Quyết định Đầu tư AI

> Thuật ngữ chuyên môn (tên bảng, biến môi trường, lệnh, đường dẫn) giữ nguyên tiếng Anh.

Tài liệu triển khai chính: `docs/DEPLOYMENT.md`.

> **Hướng dẫn triển khai chi tiết từng bước bằng tiếng Việt: [`docs/DEPLOYMENT_vi.md`](../docs/DEPLOYMENT_vi.md)** — 6 giai đoạn (chuẩn bị → hạ tầng → migration/seed → kiểm tra + dữ liệu thật → kiểm thử → vận hành) + troubleshooting. Bạn đang ở **giai đoạn 3**.
> Cập nhật 2026-09-28 (T018): scheduler **5 job** (thêm 2 cron email Mon–Fri 08:00/15:30), router `notifications` (11 thao tác); test `LLM_PROVIDER=mock MARKET_DATA_SOURCE=memory pytest -q` → kỳ vọng **551 passed, 3 skipped** (unit 523 + integration 28 liền một lệnh; chạy trên máy chủ — `tests/` không nằm trong image `api`).
> Cập nhật 2026-09-27: `ssix_finipro` (SSI FastConnect) là **nguồn chính** đã kiểm chứng (68 dòng giá + 34 dòng chỉ số); job EOD tự chuyển sang `yahoo → vndirect → tcbs → dsc` khi nguồn chính lỗi/0 dòng; `/readyz` dò thật `database`/`qdrant`/`agents` + `market_source`; image api/worker đã cài `qdrant-client` (extra `[qdrant]`).
> Cập nhật 2026-09-26: rebuild `api`/`worker` trước (scheduler 3 job + đường đọc CSDL), nạp Yahoo EOD + `compute-scores`; ĐÃ NỐI tầng suy luận LLM local (`src/agents/llm/`).

---

## Cài đặt cục bộ (MVP) — bạn đang ở bước kiểm tra + nạp dữ liệu thật

```bash
# Từ thư mục gốc repo
cp .env.example .env        # điền giá trị thật, KHÔNG BAO GIỜ commit .env

docker compose up --build -d          # api + worker + timescaledb + qdrant + dashboard
docker compose exec api alembic upgrade head
docker compose exec api python -m database.seeds.run_all
docker compose ps

# 0. Rebuild api + worker (BẮT BUỘC — scheduler + DbMarketService + SCHEDULER_*/MARKET_DATA_SOURCE mới hơn image cũ)
docker compose build api worker
docker compose up -d --no-deps api worker
docker compose logs worker 2>&1 | grep -i "registered job"   # kỳ vọng 5 job: news / EOD 15:05 / scoring 15:30 / email 08:00 / email 15:30 (T018)

# 1. EOD Việt Nam trực tiếp qua SSI FastConnect — nguồn CHÍNH (2026-09-27: fetched=68 written=68 quality=93.74)
docker compose exec -T worker python -m apps.worker.cli ingest --dataset prices \
  --source ssix_finipro --symbols FPT,VCB,HPG,ACB --start 2026-09-01 --end 2026-09-26

# 1b. Chỉ số qua SSI (Market/DailyIndex — 2026-09-27: written=34)
docker compose exec -T worker python -m apps.worker.cli ingest --dataset index_prices \
  --source ssix_finipro --indexes VNINDEX,VN30 --start 2026-09-01 --end 2026-09-26

# 1c. Dự phòng Yahoo khi SSI lỗi/hết hạn ngạch (2026-09-25: fetched=62 quality=94.88)
docker compose exec -T worker python -m apps.worker.cli ingest --dataset prices \
  --source yahoo --symbols FPT,VCB,HPG,ACB --start 2026-09-01 --end 2026-09-26

# 2. Chấm điểm trên dữ liệu thật
docker compose exec -T worker python -m apps.worker.cli compute-scores --lookback 60

# 3. Đọc lại qua API (auto → DbMarketService khi bảng prices đã có dòng)
curl -s http://localhost:8000/api/v1/stocks/FPT/ranking | head -c 600; echo
```

Endpoint:

- Tài liệu API: http://localhost:8000/docs
- Dashboard: http://localhost:8501 (8 trang gồm "Tin tức & RAG" + "📧 Quản lý Email" T018)
- Qdrant: http://localhost:6333/dashboard

## Lệnh thường dùng

```bash
docker compose logs -f api            # theo dõi log API
LLM_PROVIDER=mock MARKET_DATA_SOURCE=memory pytest -q       # kỳ vọng 2026-09-28: 551 passed, 3 skipped (chạy trên máy chủ)
LLM_PROVIDER=mock MARKET_DATA_SOURCE=db pytest tests/integration -q   # kỳ vọng: 28 passed (cần CSDL đang chạy)
./scripts/backup_db.sh                # sao lưu CSDL (backups/dtck_<timestamp>.sql.gz, giữ 14 ngày)
./scripts/health_alert.sh             # kiểm tra /healthz + /readyz (dùng cho cron/cảnh báo)
docker compose down                   # dừng (giữ volume)
docker compose down -v                # XOÁ volume (phá huỷ — mất dữ liệu!)
```

**Dashboard (T015c):** `./apps/dashboard` được bind-mount vào container nên sửa giao diện chỉ cần
`docker compose restart dashboard` (không cần rebuild). Sidebar đọc host API từ `API_HOST`
(compose đặt `http://api:8000`); huy hiệu xanh `● DỮ LIỆU THẬT — auto->db` nghĩa là dashboard
đang đọc API thật — nếu hiện huy hiệu đỏ thì client đã rơi về fixture và cần kiểm tra kết nối API.

```bash
# Kiểm tra toàn bộ 8 trang dashboard chạy được (headless, không cần trình duyệt):
docker compose exec -T -e API_HOST=http://api:8000 dashboard python -c "
from streamlit.testing.v1 import AppTest
at = AppTest.from_file('apps/dashboard/app.py', default_timeout=60); at.run()
print('exception:', at.exception)"
```

**Vận hành mô hình ML (T015b):** huấn luyện trên CSDL rồi khởi động lại API để nạp registry:

```bash
docker compose exec -T api python -m apps.worker.cli train-model --source db   # in "persisted": true
docker compose restart api                                                    # lifespan nạp lại model từ DB
curl -s localhost:8000/readyz        # kỳ vọng "models":"price_direction_xgb@1.0.0"
```

**Backfill dữ liệu dài hạn (KI-009 đã đóng):** `ingest --dataset prices --source yahoo --symbols <VN30> --start 2024-09-27 --end 2026-09-27`
→ đã đo `fetched=14810 written=14810 quality=91.87` (14.816 dòng `prices`, 30 mã). Upsert chia lô 1.000 dòng để tránh giới hạn 65.535 tham số của Postgres.

**CI:** `.github/workflows/ci.yml` chạy `ruff` + `mypy` + `pytest tests/unit` (offline) trên mỗi push/PR.

## Cấu hình runtime quan trọng (mới 2026-09-25)

| Biến | Tác dụng |
|---|---|
| `MARKET_DATA_SOURCE` | `memory` (mặc định trong code, không cần CSDL) / `db` (ép dùng TimescaleDB) / `auto` (dùng CSDL khi `prices` có dòng; compose mặc định `auto`) |
| `SCHEDULER_JOBS_ENABLED` | `true` chạy 7 job worker (news / nạp EOD 11:30 + 15:30 / chấm điểm 12:00 + 16:00 / email 08:00 + 12:30 + 16:30 / đồng bộ lịch email mỗi 15', `Asia/Ho_Chi_Minh`); `false` = tắt scheduler, vẫn nạp thủ công được |
| `SCHEDULER_NEWS_SOURCE` / `SCHEDULER_NEWS_INTERVAL_MINUTES` | mặc định `cafef` / `15` |
| `SCHEDULER_EOD_SOURCE` / `SCHEDULER_EOD_CRON_HOURS` / `SCHEDULER_EOD_CRON_MINUTE` / `SCHEDULER_EOD_LOOKBACK_DAYS` | mặc định `ssix_finipro` (chính) / `11,15` / `30` / `7` (danh sách giờ ngăn cách bởi dấu phẩy); job tự chuyển `yahoo → vndirect → tcbs → dsc` khi nguồn chính lỗi hoặc trả 0 dòng |
| `SCHEDULER_SCORING_CRON_HOURS` / `SCHEDULER_SCORING_CRON_MINUTE` | mặc định `12,16` / `0` — chấm điểm 30 phút sau mỗi lượt nạp |
| `SCHEDULER_EMAIL_SYNC_MINUTES` | mặc định `15` — chu kỳ worker đọc lại `email_schedule_configs` để lịch sửa trên dashboard áp dụng ngay, không cần restart |

Lệch DSN của worker (không chặn nếu `.env` đặt `POSTGRES_PASSWORD`): trong compose, `worker.DATABASE_URL` dự phòng bằng `dtckpassword` còn `api` dự phòng bằng `change_me` — hãy đặt mật khẩu tường minh trong `.env` để hai dịch vụ khớp nhau.

## Biến môi trường

Xem `.env.example` — không bao giờ commit secret thật.

## Sự cố đã biết / xử lý lỗi

### `alembic upgrade head` lỗi `No 'script_location' key found in configuration`

`alembic.ini` ở gốc repo (`script_location = database/migrations`) được đóng vào image API và worker cạnh các script migration, nên nó giải quyết theo `WORKDIR` của image (/app). Nếu image cũ hơn bản sửa này, hãy rebuild:

```bash
docker compose build api worker
docker compose up -d --no-deps api worker
docker compose exec -T api alembic current      # -> 0003_email_notifications (head)
```

### `FATAL: password authentication failed for user "dtck"`

`POSTGRES_PASSWORD` chỉ được đọc khi volume dữ liệu khởi tạo lần đầu, nên sửa nó trong `.env` sau đó sẽ để role trong CSDL giữ mật khẩu cũ. Hoặc khôi phục giá trị cũ trong `.env`, hoặc đồng bộ role:

```bash
docker compose exec -T db psql -U dtck -d dtck -c "ALTER USER dtck WITH PASSWORD '<mật-khẩu-trong-.env>'"
```

`docker compose down -v` cũng đặt lại được nhưng phá huỷ toàn bộ dữ liệu.

### Container không tới được `db` / `qdrant` (timeout, không phải lỗi xác thực)

Đây là vấn đề mạng ở tầng host, không phải cấu hình ứng dụng. Xác nhận gói bị chặn ở bridge của host (`docker compose exec -T api python3 -c "import socket; socket.create_connection(('db', 5432), 5)"`) rồi kiểm tra firewall host với quyền root:

```bash
sudo iptables -S FORWARD | head -40
sudo nft list ruleset | grep -i -E 'drop|reject' | head -20
sudo ebtables -L | head -20
sudo systemctl restart docker      # tạo lại bridge + luật iptables
```

### API lỗi `ModuleNotFoundError: No module named 'sklearn'`

Image API và worker cài extra `.[dev,ml]` sẵn có. `sklearn` do gói `scikit-learn` cung cấp. Gói ML cũng nạp các export huấn luyện theo kiểu lazy nên khởi động API không cần stack huấn luyện tuỳ chọn.

Sau khi cập nhật Dockerfile, hãy rebuild và tạo lại container (chỉ `restart` là không đủ):

```bash
docker compose build api worker
docker compose up -d --no-deps api worker
docker compose exec -T api python -c "import sklearn, xgboost, lightgbm; print(sklearn.__version__)"
docker compose exec -T api curl --fail http://localhost:8000/healthz
```

Các lệnh này giữ nguyên volume CSDL. Gói ML làm image lớn hơn và build lâu hơn; không cần thêm biến môi trường nào.

### Gửi email Gmail SMTP thất bại (535 / `SMTPServerDisconnected`)

Gmail SMTP **không chấp nhận mật khẩu đăng nhập thường** — phải dùng **App Password 16 ký tự**
(tạo tại `myaccount.google.com/apppasswords`, cần bật Xác thực 2 bước), rồi lưu trên dashboard
(📧 Quản lý Email → tab SMTP). Khi lưu password ≠ 16 ký tự, API trả thêm cảnh báo `warning`.
Dấu hiệu sai password: `535 5.7.8 Username and Password not accepted`; thử lại nhiều lần →
Gmail đóng kết nối (`SMTPServerDisconnected`) — API map cả hai sang hướng dẫn App Password.
Kiểm chứng kết nối SMTP trực tiếp từ container (không cần password thật):

```bash
docker compose exec -T api python -c "import socket; print(socket.create_connection(('smtp.gmail.com', 587), 10).getpeername())"
```

- **Xung đột cổng:** đổi `POSTGRES_PORT`, `API_PORT`… trong `.env`.
- **TimescaleDB chưa sẵn sàng:** worker/api `depends_on` healthcheck; chờ `pg_isready`.
- **Cài offline:** `pip install --no-index --find-links=./offline_package -r requirements-offline.txt`.
- Python cục bộ là 3.14 — nên dùng Docker để tái lập được (image ghim phiên bản).
