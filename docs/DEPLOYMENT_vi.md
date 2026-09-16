# Hướng dẫn triển khai DTCK (Tiếng Việt)

> Phiên bản: 2026-09-16 · nhánh `feat/data-source-design` · commit `edc5247`
> Bản tiếng Anh rút gọn: `helper/deployment.md` · Tài liệu chính: `docs/DEPLOYMENT.md`

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
| `POSTGRES_USER/PASSWORD/DB`, `DATABASE_URL` | ✅ | Đổi `change_me` thành mật khẩu thật |
| `QDRANT_URL` | ✅ | Mặc định `http://localhost:6333` |
| `LLM_PROVIDER`, `LLM_API_KEY` | Tùy | `mock` để chạy offline không tốn phí |
| `MARKET_DATA_PROVIDER`, `FINIPRO_ACCESS_TOKEN` | Cho dữ liệu thật | ⚠️ KI-006/007: endpoint chưa kiểm chứng, token đang trống |
| `NEWS_PROVIDER`, `NEWS_API_KEY` | Cho tin tức thật | RSS Cà phê hoạt động anonymous |

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

## Giai đoạn 3: Kiểm tra dịch vụ

```bash
# 11. API health
curl http://localhost:8000/healthz     # {"status":"ok",...}
curl http://localhost:8000/readyz      # kiểm tra dependencies (db, qdrant)

# 12. API hoạt động với dữ liệu seed
curl http://localhost:8000/api/v1/market/indices
curl http://localhost:8000/api/v1/predictions/FPT

# 13. Swagger UI tương tác   → http://localhost:8000/docs
# 14. Dashboard              → http://localhost:8501
# 15. Qdrant dashboard       → http://localhost:6333/dashboard
```

⚠️ **Lưu ý quan trọng (KI-008):** ở thời điểm hiện tại API phục vụ dữ liệu tổng hợp in-memory từ `MarketService`, chưa đọc từ TimescaleDB. Migration + seed ở Giai đoạn 2 là nền tảng, nhưng việc nối routers vào repository SQL chưa thực hiện.

---

## Giai đoạn 4: Dữ liệu thị trường

**Lựa chọn A — Offline/fixture (mặc định, không cần mạng):**

```bash
# 16. Nạp giá EOD từ fixture (deterministic, phục vụ test/demo)
docker compose exec api python -m apps.worker.cli ingest \
    --dataset prices --source fixture \
    --start 2026-09-01 --end 2026-09-05 --symbols FPT,VCB,HPG
```

**Lựa chọn B — Provider thật (bị chặn, xem KI-006/007):**

1. Điền `FINIPRO_ACCESS_TOKEN` trong `.env`
2. Kiểm chứng endpoint SSI FiniPro (chưa ai xác minh được — không có egress khi thiết kế)
3. Chạy lại ingest với `--source ssix_finipro`
4. **Quality gate §39**: batch dưới 80 điểm sẽ bị flag `below_threshold` và command trả exit code 1 — đây là hành vi đúng, không phải lỗi

**Worker scheduler:** container `worker` chạy APScheduler blocking (chưa đăng ký job định kỳ — cần bổ sung nếu muốn ingest tự động hàng ngày).

**Huấn luyện mô hình ML (T014):**

```bash
# Lệnh CLI train-model — trên fixture tổng hợp hiện tại sẽ từ chối
# một cách trung thực vì 100% nhãn 5 ngày đều dương (KI-012)
docker compose exec api python -m apps.worker.cli train-model
```

---

## Giai đoạn 5: Xác thực chất lượng triển khai

```bash
# 17. Chạy toàn bộ test suite trong container
docker compose exec api pytest -q          # kỳ vọng: 325 passed

# 18. Lint + type check (image API cài kèm dev deps)
docker compose exec api ruff check .
docker compose exec api mypy
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

| # | Việc | Trạng thái |
|---|---|---|
| 1 | **T015** — JWT/RBAC thật (login hiện là demo token), rate limiting, audit, CI/CD | Chưa làm |
| 2 | **KI-008** — nối routers vào repository SQLAlchemy (thay `get_market_service()` trong `apps/api/dependencies.py`) | Chưa làm |
| 3 | **KI-012** — ML huấn luyện thật cần dữ liệu giá hỗn hợp tăng/giảm; hiện fixture chỉ tăng → `train-model` từ chối đúng | Chờ #2 + dữ liệu thật |
| 4 | HTTPS/reverse proxy (nginx/traefik) + secrets manager | Chưa có trong compose |
| 5 | Backup DB định kỳ (cron + `pg_dump`) | Chưa cấu hình |

---

## Troubleshooting nhanh

| Triệu chứng | Nguyên nhân / cách xử lý |
|---|---|
| Port đã được sử dụng | Đổi `POSTGRES_PORT` / `API_PORT` / `DASHBOARD_PORT` trong `.env` |
| `alembic upgrade` lỗi kết nối | DB chưa healthy — đợi `pg_isready`, xem `docker compose logs db` |
| `readyz` báo qdrant offline | Bình thường khi không có `qdrant_client` — RAG dùng index in-memory (KI-011) |
| Ingest trả exit 1 | Quality gate §39 từ chối batch kém chất lượng — xem log `validation issue` |
| `train-model` lỗi "single class" | KI-012 — fixture tổng hợp chỉ tăng; cần dữ liệu thật |
