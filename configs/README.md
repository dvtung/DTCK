# configs/

Cấu hình lúc chạy (runtime configuration). Mật mã / secret TUYỆT ĐỐI KHÔNG lưu ở đây (xem `.env` / secret store).

## Các tệp cấu hình

- `scoring_weights.yaml` — trọng số nhân tố cơ sở (spec §12, có đánh số phiên bản).
- `sources.yaml` — danh mục provider dữ liệu (T002; thiết kế trong `docs/DATA_SOURCES_vi.md`):
  id của provider, vai trò, mô hình xác thực, **tên** biến môi trường chứa credential (không bao giờ lưu giá trị thật),
  cờ kích hoạt/độ ưu tiên, lựa chọn theo từng miền dữ liệu và chuỗi dự phòng (fallback).
- Chỗ giữ chỗ cho tương lai: `universe.yaml` (ảnh chụp danh sách thành viên VN30/VN100),
  `agents.yaml` (danh mục agent).

## Trọng số chấm điểm

Các trọng số cơ sở là **giả định cần được kiểm chứng thông qua kiểm nghiệm lịch sử (backtesting)** (§12).
Thay đổi trọng số đồng nghĩa với tạo một `scoring_version` mới, không bao giờ sửa trực tiếp phiên bản đã triển khai.
