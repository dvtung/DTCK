# Các bản sửa đổi Alembic (Migrations)

Bản migration ban đầu: `versions/0001_initial_schema.py` (BƯỚC 2 THIẾT KẾ CSDL)
tạo toàn bộ các bảng từ `src.common.models.Base.metadata` và chuyển các bảng
chuỗi thời gian thành hypertable của TimescaleDB (xem `docs/DATABASE_SCHEMA_vi.md` §17).

```bash
alembic upgrade head      # áp dụng tất cả migrations (cần DATABASE_URL hợp lệ)
alembic downgrade base    # xóa/hạ tất cả các bảng
python -m database.seeds.run_all   # nạp dữ liệu mầm: sàn GD / lĩnh vực / ngành / VN30
```
