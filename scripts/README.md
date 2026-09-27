# scripts/

Các script vận hành (mặc định chạy tại thư mục gốc repository).

Kế hoạch phát triển:
- `bootstrap.sh`      — tạo `.env` từ `.env.example`, khởi tạo pre-commit
- `run_collector.sh`  — script thu thập dữ liệu một lần (bọc `apps.worker.cli`)
- `backtest_cli.py`   — chạy kiểm nghiệm lịch sử từ cấu hình (Giai đoạn 3)
- `train_cli.py`      — huấn luyện + đăng ký mô hình (Giai đoạn 6)
- `export_offline.sh` — tái tạo gói wheel cho `offline_package`

Đã có (2026-09-27):
- `backup_db.sh`    — sao lưu `pg_dump` + gzip vào `backups/`, chính sách giữ `RETENTION_DAYS` ngày
- `health_alert.sh` — kiểm tra `/healthz` + `/readyz` qua HTTP, thoát mã ≠ 0 khi có sự cố (chạy qua cron)

Hiện tại các tác vụ vận hành trực tiếp được thực hiện thông qua module CLI `apps.worker.cli` và các công cụ Docker/Alembic tương ứng.
