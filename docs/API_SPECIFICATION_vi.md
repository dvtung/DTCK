# ĐẶC TẢ API (Bản tiếng Việt)

## Nền tảng Nghiên cứu & Quyết định Đầu tư AI

> Thuật ngữ chuyên môn (tên bảng, API, mã nguồn) giữ nguyên tiếng Anh.

**Phiên bản:** 1.0 (dự thảo)
**Trạng thái:** Cơ sở — suy ra từ SYSTEM_SPECIFICATION.md v1.0 (§28)

> Trạng thái triển khai 2026-09-28: 13 tệp router, **48 đường dẫn / 53 thao tác** trên `/api/v1/*`
> (không tính `/healthz` + `/readyz` + `/metrics`); xem trang tương tác `docs/api.html`.

---

# 1. Quy ước

- Đường dẫn gốc: `/api/v1`
- Định dạng: JSON, `application/json`
- Lỗi: `{ "error": { "code": str, "message": str, "details": optional } }` với mã HTTP chuẩn
- Phân trang: query param `limit` (mặc định 20, tối đa 200), `offset` (mặc định 0); response gồm `{ "items": [...], "total": n, "limit": l, "offset": o }`
- **Hiệu năng (§45):** endpoint không LLM nhắm P95 < 500 ms — độ trễ LLM không tính vào ngân sách API lõi.

- **Quy mô hợp đồng (2026-09-28, lấy từ `app.openapi()`):** **48 đường dẫn / 53 thao tác** trên `/api/v1/*` (không tính `/healthz` + `/readyz` + `/metrics`; cộng 3 đường hệ thống = 51 đường dẫn / 56 thao tác). Router `notifications` (T018) đóng góp 11 thao tác.

---

# 2. Nhóm API (§28)

## 2.1. `/api/v1/market`

| Method | Path | Mô tả |
|---|---|---|
| GET | `/market/indices` | snapshot chỉ số (VNINDEX, VN30, …) |
| GET | `/market/indices/{code}` | snapshot một chỉ số |
| GET | `/market/indices/{code}/prices` | chuỗi OHLCV ngày của chỉ số (nến VNINDEX, T016) |
| GET | `/market/regime` | chế độ thị trường hiện tại + độ tin cậy (§13) |
| GET | `/market/regime/history` | lịch sử chế độ |
| GET | `/market/breadth` | số mã tăng/giảm, độ lan tỏa |
| GET | `/market/movers` | top tăng/giảm `?universe=VN100\|VN30\|HNX\|UPCOM&limit=10` kèm `%1D`, khoảng cách MA20/MA50 (T016) |

## 2.2. `/api/v1/stocks`

| Method | Path | Mô tả |
|---|---|---|
| GET | `/stocks` | danh sách mã + bộ lọc (sàn, ngành, universe VN30/VN100) |
| GET | `/stocks/{symbol}` | hồ sơ + snapshot mới nhất |
| GET | `/stocks/{symbol}/prices` | chuỗi OHLCV (start/end, cờ adjusted) |
| GET | `/stocks/{symbol}/ranking` | thứ hạng + phân rã điểm (§43) |
| GET | `/stocks/ranked` | xếp hạng universe kèm điểm |

## 2.3. `/api/v1/fundamentals`

| Method | Path | Mô tả |
|---|---|---|
| GET | `/fundamentals/{symbol}/statements` | KQKD/CĐKT/lưu chuyển tiền + lọc kỳ |
| GET | `/fundamentals/{symbol}/ratios` | lịch sử hệ số |
| GET | `/fundamentals/{symbol}/quality` | điểm chất lượng dữ liệu + trạng thái (§39) |

## 2.4. `/api/v1/technical`

| Method | Path | Mô tả |
|---|---|---|
| GET | `/technical/{symbol}/indicators` | RSI, MACD, MA, Bollinger, ATR, ADX… |
| GET | `/technical/{symbol}/features` | dòng feature-store (lọc feature_version) |

## 2.5. `/api/v1/valuation`

| Method | Path | Mô tả |
|---|---|---|
| GET | `/valuation/{symbol}/summary` | P/E, P/B, EV/EBITDA, DY, PEG + phân vị ngành |
| GET | `/valuation/{symbol}/history` | dải định giá lịch sử |

## 2.6. `/api/v1/news`

| Method | Path | Mô tả |
|---|---|---|
| GET | `/news` | lọc: mã, ngành, khoảng ngày, nguồn, sentiment |
| POST | `/news/search` | tìm lai RAG → tập bằng chứng (§18.2, §19) |

## 2.7. `/api/v1/analysis`

| Method | Path | Mô tả |
|---|---|---|
| POST | `/analysis/request` | xếp hàng lượt phân tích agent (bất đồng bộ) |
| GET | `/analysis/request/{agent_run_id}` | trạng thái + kết quả (`InvestmentAnalysis` có cấu trúc) |
| GET | `/analysis/{symbol}/latest` | phân tích mới nhất đã lưu |

Mẫu bất đồng bộ: POST trả `202 + { agent_run_id }`; poll GET tới `SUCCESS/FAILED/TIMEOUT` (§45).

## 2.8. `/api/v1/predictions`

| Method | Path | Mô tả |
|---|---|---|
| GET | `/predictions/{symbol}` | dự báo đã lưu (lọc model/chân trời) |
| GET | `/predictions/evaluations` | theo dõi kết quả thực (§26) |

## 2.9. `/api/v1/portfolio`

| Method | Path | Mô tả |
|---|---|---|
| GET | `/portfolio/summary` | giá trị, độ phủ, tập trung, sụt giảm (§27) |
| GET | `/portfolio/positions` | vị thế + tín hiệu kiểm tra |

## 2.10. `/api/v1/backtests`

| Method | Path | Mô tả |
|---|---|---|
| POST | `/backtests` | tạo/chạy backtest (tham số sync hoặc async) |
| GET | `/backtests` | liệt kê lượt chạy |
| GET | `/backtests/{id}` | tổng quan + tham số |
| GET | `/backtests/{id}/metrics` | bảng chỉ số (§15) |
| GET | `/backtests/{id}/trades` | nhật ký lệnh |

## 2.11. `/api/v1/agents`

| Method | Path | Mô tả |
|---|---|---|

## 2.12. `/api/v1/notifications` (T018)

| Method | Path | Mô tả |
|---|---|---|
| GET | `/notifications/recipients` | danh sách email nhận báo cáo định kỳ (`?active_only=`) |
| POST | `/notifications/recipients` | thêm/kích hoạt email nhận mới |
| PATCH | `/notifications/recipients/{id}` | bật/tắt trạng thái nhận |
| DELETE | `/notifications/recipients/{id}` | xóa email khỏi danh sách |
| GET | `/notifications/smtp` | thông tin tài khoản SMTP gửi (mật khẩu bị ẩn) |
| POST | `/notifications/smtp` | lưu cấu hình SMTP Gmail (server, port, email, app password) |
| GET | `/notifications/schedule` | cấu hình giờ gửi tự động 3 khung (sáng 08:00, trưa 12:30, chiều 16:30, Mon-Fri) |
| POST | `/notifications/schedule` | cập nhật lịch gửi tự động |
| POST | `/notifications/send-test` | gửi email thử nghiệm ngay lập tức đến địa chỉ chỉ định |
| GET | `/notifications/preview-html` | xem trước HTML báo cáo tổng quan thị trường |
| GET | `/notifications/logs` | nhật ký các lượt gửi email (SUCCESS/FAILED) |

| GET | `/agents` | liệt kê registry (phiên bản, trạng thái, tool) |
| GET | `/agents/runs` | lịch sử chạy (§31) |
| GET | `/agents/runs/{agent_run_id}` | bản ghi audit đầy đủ: prompt, tool call, token, độ trễ |

---

# 3. Xác thực & Phân quyền (Production)

- `POST /api/v1/auth/login` → JWT (access + refresh). Sai credential → **401** với
  phong bì lỗi `invalid_credentials` (MVP không DB so với danh tính demo tất định
  qua `secrets.compare_digest`; production thay bằng phát hành JWT, §32).
- API key: `Authorization: Bearer <api_key>`; DB chỉ lưu `key_hash` (§32, xem SECURITY.md).
- Role RBAC: `ADMIN`, `ANALYST`, `VIEWER`.
- Giới hạn tần suất theo user/key trên endpoint dùng LLM (kiểm soát chi phí §47).

---

# 4. Hành vi chung

- **Độ tươi dữ liệu:** response gồm `data_timestamp` / `as_of`; guardrail gắn cờ dữ liệu cũ (§42).
- **Bằng chứng:** endpoint suy ra từ LLM trả `evidence: [Evidence]` và `confidence`; không bao giờ trả số trần không nguồn tất định.
- **Tất định:** endpoint quant/định giá/kỹ thuật đọc thuần từ kho tính trước; đường nóng không tính toán lúc request.
