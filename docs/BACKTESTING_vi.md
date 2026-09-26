# BACKTESTING — KIỂM THỬ NGƯỢC (Bản tiếng Việt)

## Nền tảng Nghiên cứu & Quyết định Đầu tư AI

> Thuật ngữ chuyên môn (tên bảng, API, mã nguồn) giữ nguyên tiếng Anh.

**Phiên bản:** 1.0
**Trạng thái:** Cơ sở — suy ra từ SYSTEM_SPECIFICATION.md v1.0 (§16, §17)

---

# 1. Vai trò

Backtesting là **thành phần hạ tầng hạng nhất** (ADR-007), không phải tiện ích gắn thêm.

> Một chiến lược/model chưa sẵn sàng production cho tới khi được kiểm chứng trên dữ liệu lịch sử phù hợp (§4.5).
> "Không có bước này thì không cho phép hệ thống tự tin đưa ra signal."

---

# 2. Luồng (§16)

```text
Dữ liệu lịch sử
      ↓
Sinh đặc trưng       (tái diễn as-of — không nhìn trước)
      ↓
Sinh tín hiệu
      ↓
Dựng danh mục       (luật universe, cỡ vị thế, trọng số)
      ↓
Mô phỏng khớp lệnh  (vào/ra ở bar kế tiếp, logic fill)
      ↓
Chi phí giao dịch   (phí + spread + trượt giá, bps)
      ↓
Hiệu quả            (chỉ số ở §3 dưới)
```

---

# 3. Chỉ số hiệu quả (§15 chỉ số đầu tư)

```text
CAGR
Sharpe
Sortino
Calmar
Maximum Drawdown
Win Rate
Profit Factor
Turnover
Transaction Cost
```

Lưu trong `backtest_metrics` theo từng lượt chạy. **Không bao giờ đánh giá model chỉ bằng độ chính xác dự báo** (§15).

---

# 4. Chống thiên lệch (§17)

| Thiên lệch | Biện pháp |
|---|---|
| Nhìn trước (look-ahead) | tái diễn dữ liệu as-of với `valid_from/valid_to` lưỡng thời (báo cáo tài chính), đặc trưng chỉ tính từ dữ liệu có tại `t` |
| Sống sót (survivorship) | universe lịch sử từ `listed_date/delisted_date`, giữ mã đã hủy niêm yết |
| Rò rỉ dữ liệu (leakage) | chia train/validation/test nghiêm + walk-forward; không thông tin tương lai trong đặc trưng |
| Overfitting | đánh giá in-sample / out-of-sample / walk-forward / rolling window; phân tích độ nhạy tham số |

Kiểm soát bổ sung: chi phí giao dịch, trượt giá, sự kiện doanh nghiệp (tách/cổ tức qua `adjusted_prices`).

---

# 5. Chế độ (§16)

| Chế độ | Ý nghĩa |
|---|---|
| In-sample | train & test cùng cửa sổ (chỉ làm baseline) |
| Out-of-sample | tập giữ lại chưa từng động tới |
| Walk-forward | lăn train → test tiến, lặp lại |
| Rolling window | cửa sổ trượt cỡ cố định |

Loại lượt chạy lưu trong `backtests.run_type`.

---

# 6. Mô phỏng khớp lệnh

- Tín hiệu sinh ngày `t` từ dữ liệu đóng cửa `t` → lệnh khớp ở giá mở cửa `t+1` (tránh nhìn trước).
- Chi phí giao dịch: `commission_bps + slippage_bps` tính trên **mỗi fill** (cả vào và ra),
  trừ vào tiền mặt; engine báo tổng đã trừ chính xác là `transaction_cost` (không suy ngược từ trade log).
- Tổng trọng số mục tiêu phải ≤ 1.0 (chỉ long, không margin ngầm); lượt chạy vượt sẽ raise lỗi.
- Fill xếp **bán trước mua sau** để tiền bán giải phóng kịp cho tái cân bằng.
- **Dải không-giao-dịch** (`MIN_REBALANCE_PCT = 0.5%` giá trị danh mục) bỏ qua drift tái cân bằng
  không đáng kể thay vì đốt phí cho lệnh vụn.
- Thoát một phần ghi **chỉ lượng đã bán**; phần còn lại giữ nguyên giá/ngày vào.
  Mua thêm gộp vào chân lệnh đang mở theo giá vào bình quân khối lượng (kế toán giá vốn bình quân).
- Điểm equity cuối được đánh dấu lại **sau** thanh lý cuối cửa sổ, nên `final_equity()`
  đã gồm chi phí đóng vị thế.
- Sự kiện doanh nghiệp áp qua giá điều chỉnh để lợi nhuận liên tục.

---

# 7. Mô hình lưu trữ

Xem `docs/DATABASE_SCHEMA.md` §11:

- `backtests` — định nghĩa + tham số + chi phí lượt chạy
- `backtest_trades` — mọi lệnh vào/ra kèm giá, khối lượng, PnL
- `backtest_metrics` — cặp tên/giá trị chỉ số

---

# 8. Điều kiện bảo vệ khi triển khai

Một chiến lược chỉ đủ điều kiện lên **signal** khi:

```text
qua cổng chất lượng dữ liệu (§39)   VÀ
qua kiểm walk-forward out-of-sample   VÀ
chỉ số điều chỉnh rủi ro sau chi phí dương   VÀ
đã lập tài liệu độ nhạy tham số
```

Ngược lại giữ `EXPERIMENTAL` và không bao giờ hiện thành signal production.
