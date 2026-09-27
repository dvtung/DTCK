# BẢO MẬT (Bản tiếng Việt)

## Nền tảng Nghiên cứu & Quyết định Đầu tư AI

> Thuật ngữ chuyên môn (tên bảng, API, mã nguồn) giữ nguyên tiếng Anh.

**Phiên bản:** 1.0
**Trạng thái:** Cơ sở — suy ra từ SYSTEM_SPECIFICATION.md v1.0 (§32, §41)

---

# 1. Chính sách

- **Không có API key, mật khẩu hay secret** trong mã nguồn, lịch sử Git hay Docker image (§32).
- Mọi secret chỉ đến từ biến môi trường / secret manager.
- Role ứng dụng có **quyền tối thiểu** cần thiết; kết nối dùng credential CSDL riêng biệt.

---

# 2. Quản lý Secret

| Tầng | Quy tắc |
|---|---|
| Mã nguồn | không secret; biến qua pydantic-settings + `.env` (không commit) |
| Repo | `.env`, `*.pem`, `*.key` bị git-ignore; `.env.example` chỉ ghi tên biến |
| Docker | secret bơm qua Compose `env_file`/`secrets` hoặc biến môi trường, không bao giờ bake vào image |
| Production | secret manager (dựa trên env hoặc kho secret cloud) |

---

# 3. Bảo mật API

- **Xác thực:** JWT (access/refresh) cho người dùng; API key băm cho truy cập lập trình — chỉ lưu `key_hash`, không bao giờ lưu key thô.
  - *Triển khai (T015b):* `apps/api/security.py` cấp/kiểm JWT HS256 (thư viện chuẩn, không thêm dependency) với TTL `AUTH_JWT_SECRET`; middleware ghi nhận cả API key (`API_AUTH_KEY`) cả JWT hợp lệ; khoá đều để trống ở môi trường demo/unit test (danh tính ADMIN offline có tài liệu). Lưu `key_hash` vào bảng `api_keys` và đối chiếu `users` là việc còn lại.
- **Phân quyền:** RBAC — `ADMIN`, `ANALYST`, `VIEWER`; ép buộc ở tầng dependency theo route trong FastAPI.
  - *Triển khai (T015b):* `require_roles(...)` trên `POST /api/v1/backtests` (VIEWER → 403); token giả ký bị middleware chặn trước khi tới route.
- **Giới hạn tần suất:** theo key/user, chặt hơn với endpoint dùng LLM (§47 kiểm soát chi phí).
- **Kiểm tra đầu vào:** schema Pydantic ở biên; từ chối field lạ; kiểu strict.

---

# 4. Bảo mật CSDL

- Tách user DB: `api_ro` (chỉ đọc), `api_rw` (ghi ứng dụng), `migration` (chỉ DDL), credential riêng qua env.
- `audit_logs` **chỉ ghi thêm (append-only)**: role API/migration chỉ có `INSERT/SELECT`, không `UPDATE/DELETE` (§31, §41 cấm agent xóa audit log).
- TLS cho kết nối DB ở môi trường không phải local.
- TimescaleDB/Postgres chạy trong Docker network riêng (production không publish ra host).

---

# 5. Bảo mật Agent / LLM (§41 Quản trị Agent)

Agent bị cấm tuyệt đối:
- Đổi schema CSDL
- Đổi model / trọng số chấm điểm
- Thực hiện giao dịch
- Xóa audit log

Tầng tool là đường duy nhất tới DB — LLM không có kết nối trực tiếp (§22). Output của tool được kiểm tra/schema-validate trước khi trả về LLM hoặc lưu trữ (ADR-006).

---

# 6. Kiểm toán (§31)

Mỗi lượt chạy agent lưu: yêu cầu người dùng, agent, model + phiên bản, phiên bản prompt, tool đã gọi, input/output tool, bằng chứng, output cuối, timestamp, độ trễ, token đã dùng. Dữ liệu audit phục vụ tái lập, debug, đánh giá và tuân thủ.

---

# 7. Bảo vệ dữ liệu

- Credential và token không bao giờ truyền tới dịch vụ ngoài; egress proxy/whitelist quản lý kết nối LLM & nguồn dữ liệu.
- Backup vector/DB (WAL + dump nightly) thuộc định nghĩa Production (§52).
- Secret thô lọt vào log/code phải che ngay (quy tắc toàn cục 0.4).
