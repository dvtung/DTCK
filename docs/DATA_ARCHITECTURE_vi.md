# KIẾN TRÚC DỮ LIỆU (Bản tiếng Việt)

## Nền tảng Nghiên cứu & Quyết định Đầu tư AI

> Thuật ngữ chuyên môn (tên bảng, API, mã nguồn) giữ nguyên tiếng Anh.

**Phiên bản:** 1.0
**Trạng thái:** Cơ sở — suy ra từ SYSTEM_SPECIFICATION.md v1.0 (§9, §10)

---

# 1. Miền dữ liệu (§10)

| Miền | Bảng (PostgreSQL) | Qdrant | Ghi chú |
|---|---|---|---|
| Dữ liệu thị trường | `prices`, `adjusted_prices`, `index_prices`, `foreign_flows`, `prop_trading_flows` | — | OHLCV EOD, giá trị, vốn hóa, khối ngoại/tự doanh |
| Cơ bản | `financial_statements`, `financial_ratios` | — | báo cáo lưỡng thời (điều chỉnh hồi tố), hệ số tính trước |
| Định giá | `valuation_daily` | — | P/E, P/B, EV/EBITDA, EV/Sales, DY, PEG theo ngày |
| Kỹ thuật | `features` | — | SMA, EMA, RSI, MACD, Bollinger, ATR, ADX… |
| Vĩ mô | `macro_indicators` | — | GDP, CPI, lãi suất, FX, tăng trưởng tín dụng, M2 |
| Sự kiện doanh nghiệp | `corporate_events` | payload nhúng được | KQKD, cổ tức, tách, quyền, ĐHĐCĐ, M&A, pháp lý |
| Tin tức | `news`, `news_symbols` | full item + embedding | tiêu đề, nội dung, sentiment, độ quan trọng, liên kết mã |
| Tín hiệu | `signals` | — | tất định, phiên bản hóa |
| Đặc trưng | `features` | — | kho đặc trưng (0..n mỗi mã/ngày), phiên bản hóa feature_version |

---

# 2. Luồng nạp dữ liệu (STEP 3 của đặc tả §57)

```text
Nguồn
  ↓
Collector          → fetch, phân trang, giới hạn tần suất, auth
  ↓
Validator          → kiểm schema, null, khoảng, duy nhất, đơn điệu, độ tươi nguồn
  ↓
Normalizer         → ánh xạ mã/sàn, tiền tệ, hệ số điều chỉnh, khử trùng
  ↓
PostgreSQL         → upsert idempotent (ON CONFLICT DO UPDATE nếu nguồn cho phép)
```

- Chạy trong app **worker** qua APScheduler (job EOD; intraday sau).
- Mỗi batch ghi provenance: `source`, `ingested_at`, id batch.
- **Retry + xử lý lỗi + cảnh báo** theo §8.1.

---

# 3. Khung chất lượng dữ liệu (§39)

Mỗi dataset chấm 0–100 trên sáu chiều vào `data_quality_scores`:

| Chiều | Định nghĩa | Ví dụ kiểm |
|---|---|---|
| Completeness (đầy đủ) | % dòng kỳ vọng có mặt | ngày giao dịch x universe |
| Accuracy (chính xác) | sai số vs chuẩn tin cậy | đối chiếu OHLC với feed sàn |
| Consistency (nhất quán) | gắn kết chéo nội bộ | high ≥ low ≥ biên close/open |
| Freshness (tươi) | tuổi dữ liệu mới nhất vs kỳ vọng | trade_date cuối == phiên gần nhất |
| Uniqueness (duy nhất) | tỉ lệ trùng | trùng (stock_id, trade_date) |
| Validity (hợp lệ) | vi phạm miền/ràng buộc | giá > 0, khối lượng ≥ 0 |

**Cổng:** nếu `overall_score < threshold` → đánh `below_threshold = true` → dataset **không dùng cho dự báo/backtest** (§39). Giữ dữ liệu thô để tái xử lý; không bao giờ lặng lẽ xóa.

---

# 4. Xử lý dữ liệu thị trường

- `prices` lưu OHLCV **thô** đúng như nhận (giữ `source`, `ingested_at`).
- `adjusted_prices` lưu `adj_factor`, `adj_close` tính qua feed sự kiện doanh nghiệp — không bao giờ sửa thô (§4.1, §4.2 nguyên tắc thiết kế).
- `index_prices` cho chỉ số VNINDEX / VN30 / HNX / UPCOM — dùng bởi Market Regime Engine (§13).
- **Kiểm soát thiên lệch sống sót (§17):** mã hủy niêm yết ở lại `stocks` với `status='DELISTED'`; dựng universe lịch sử dùng `listed_date`/`delisted_date`.

---

# 5. Tính lưỡng thời báo cáo tài chính (§5.1 DATABASE_SCHEMA)

- Cửa sổ `valid_from`/`valid_to` cho mỗi (báo cáo, chỉ tiêu).
- Mọi consumer phải truy vấn as-of: `valid_from <= as_of < COALESCE(valid_to, 'infinity')`.
- Bắt buộc với backtester — chống thiên lệch nhìn trước từ báo cáo điều chỉnh (§17).

---

# 6. Phiên bản hóa tín hiệu & đặc trưng

| Khái niệm | Trường | Quy ước |
|---|---|---|
| Phiên bản dữ liệu | `source` + `ingested_at` | theo batch |
| Phiên bản đặc trưng | `feature_version` | tăng khi đổi cách tính (vd `technical_1.0`) |
| Phiên bản chấm điểm | `scoring_version` | phiên bản bộ trọng số (vd `baseline_1.0`) |
| Phiên bản model | `model_registry.version` | gắn với dữ liệu huấn luyện + phiên bản đặc trưng (§40) |

Bất biến:

> Một dự báo phải tái lập được khi cho `(stock, trade_date, data_version, feature_version, model_id, model_version)`.

---

# 7. Tóm tắt công nghệ lưu trữ

| Kho | Công nghệ | Mục đích |
|---|---|---|
| Quan hệ/chuỗi thời gian | PostgreSQL + TimescaleDB | mọi dữ liệu có cấu trúc, hypertable (§17 schema DB) |
| Vector | Qdrant | embedding tài liệu/tin tức + lọc metadata |
| Đối tượng (tương lai) | tương thích S3 | PDF thô, artifact backtest, snapshot (§9.3) |
| Cache (tương lai) | Redis | cache API tùy chọn ngoài MVP |

---

# 8. Chiến lược migration & seed

- Migration **Alembic** trong `database/migrations/`; một thay đổi logic một migration; bất biến khi đã merge.
- Tạo hypertable TimescaleDB ngay trong cùng migration tạo bảng.
- Seed trong `database/seeds/`: sàn (HOSE/HNX/UPCOM), phân loại ngành, snapshot thành viên VN30/VN100.
- Xem `docs/DATABASE_SCHEMA.md` §18.
