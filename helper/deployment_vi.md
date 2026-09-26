# Hướng dẫn triển khai (helper) — Bản tiếng Việt

## Nền tảng Nghiên cứu & Quyết định Đầu tư AI

> Thuật ngữ chuyên môn (tên bảng, biến môi trường, lệnh, đường dẫn) giữ nguyên tiếng Anh.

Tài liệu triển khai chính: `docs/DEPLOYMENT.md`.

> **Hướng dẫn triển khai chi tiết từng bước bằng tiếng Việt: [`docs/DEPLOYMENT_vi.md`](../docs/DEPLOYMENT_vi.md)** — 6 giai đoạn (chuẩn bị → hạ tầng → migration/seed → kiểm tra + dữ liệu thật → kiểm thử → vận hành) + troubleshooting. Bạn đang ở **giai đoạn 3**.
> Cập nhật 2026-09-26: rebuild `api`/`worker` trước (scheduler 3 job + đường đọc CSDL), nạp Yahoo EOD + `compute-scores`; kỳ vọng **422 passed, 3 skipped**.

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
docker compose logs worker 2>&1 | grep -i "registered job"   # kỳ vọng 3 job: news / EOD 15:05 / scoring 15:30

# 1. EOD Việt Nam trực tiếp (đã kiểm chứng 2026-09-25: fetched=62 written=62 quality=94.88)
docker compose exec -T worker python -m apps.worker.cli ingest --dataset prices \
  --source yahoo --symbols FPT,VCB,HPG,ACB --start 2026-09-01 --end 2026-09-25

# 2. Chấm điểm trên dữ liệu thật
docker compose exec -T worker python -m apps.worker.cli compute-scores --lookback 60

# 3. Đọc lại qua API (auto → DbMarketService khi bảng prices đã có dòng)
curl -s http://localhost:8000/api/v1/stocks/FPT/ranking | head -c 600; echo
```

Endpoint:

- Tài liệu API: http://localhost:8000/docs
- Dashboard: http://localhost:8501 (trang mới "Tin tức & RAG")
- Qdrant: http://localhost:6333/dashboard

## Lệnh thường dùng

```bash
docker compose logs -f api            # theo dõi log API
docker compose exec -T api sh -c "LLM_PROVIDER=mock pytest -q"   # kỳ vọng 422 passed, 3 skipped
docker compose down                   # dừng (giữ volume)
docker compose down -v                # XOÁ volume (phá huỷ — mất dữ liệu!)
```

## Cấu hình runtime quan trọng (mới 2026-09-25)

| Biến | Tác dụng |
|---|---|
| `MARKET_DATA_SOURCE` | `memory` (mặc định trong code, không cần CSDL) / `db` (ép dùng TimescaleDB) / `auto` (dùng CSDL khi `prices` có dòng; compose mặc định `auto`) |
| `SCHEDULER_JOBS_ENABLED` | `false` tắt 3 job worker (news / EOD 15:05 / scoring 15:30 ICT, `Asia/Ho_Chi_Minh`); vẫn nạp thủ công được |
| `SCHEDULER_NEWS_SOURCE` / `SCHEDULER_NEWS_INTERVAL_MINUTES` | mặc định `cafef` / `15` |
| `SCHEDULER_EOD_SOURCE` / `SCHEDULER_EOD_CRON_HOUR` / `SCHEDULER_EOD_CRON_MINUTE` / `SCHEDULER_EOD_LOOKBACK_DAYS` | mặc định `yahoo` / `15` / `5` / `7` |
| `SCHEDULER_SCORING_CRON_HOUR` / `SCHEDULER_SCORING_CRON_MINUTE` | mặc định `15` / `30` |

Lệch DSN của worker (không chặn nếu `.env` đặt `POSTGRES_PASSWORD`): trong compose, `worker.DATABASE_URL` dự phòng bằng `dtckpassword` còn `api` dự phòng bằng `change_me` — hãy đặt mật khẩu tường minh trong `.env` để hai dịch vụ khớp nhau.

## Biến môi trường

Xem `.env.example` — không bao giờ commit secret thật.

## Sự cố đã biết / xử lý lỗi

### `alembic upgrade head` lỗi `No 'script_location' key found in configuration`

`alembic.ini` ở gốc repo (`script_location = database/migrations`) được đóng vào image API và worker cạnh các script migration, nên nó giải quyết theo `WORKDIR` của image (/app). Nếu image cũ hơn bản sửa này, hãy rebuild:

```bash
docker compose build api worker
docker compose up -d --no-deps api worker
docker compose exec -T api alembic current      # -> 0001_initial_schema (head)
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

- **Xung đột cổng:** đổi `POSTGRES_PORT`, `API_PORT`… trong `.env`.
- **TimescaleDB chưa sẵn sàng:** worker/api `depends_on` healthcheck; chờ `pg_isready`.
- **Cài offline:** `pip install --no-index --find-links=./offline_package -r requirements-offline.txt`.
- Python cục bộ là 3.14 — nên dùng Docker để tái lập được (image ghim phiên bản).
