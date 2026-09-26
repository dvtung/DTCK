# KIẾN TRÚC ML (Bản tiếng Việt)

## Nền tảng Nghiên cứu & Quyết định Đầu tư AI

> Thuật ngữ chuyên môn (tên bảng, API, mã nguồn) giữ nguyên tiếng Anh.

**Phiên bản:** 1.0
**Trạng thái:** Cơ sở — suy ra từ SYSTEM_SPECIFICATION.md v1.0 (§14, §15, §26)

---

# 1. Tôn chỉ

- LLM **không phải** engine dự báo chính (§14). Dự báo là việc của model huấn luyện cổ điển.
- Công cụ ban đầu: **XGBoost, LightGBM, Scikit-learn**.
- Model chỉ được dùng sau khi huấn luyện/kiểm chứng/hiệu chuẩn đúng + đăng ký registry (§40).

> Trạng thái triển khai: T014 xong pipeline (dataset + training + calibration + registry + API `/predictions`);
> huấn luyện thật đang chờ dữ liệu giá hỗn hợp tăng/giảm (KI-012) — `train-model` hiện từ chối trung thực trên fixture chỉ tăng.

---

# 2. Phát biểu bài toán

| Mục tiêu | Loại | Chân trời |
|---|---|---|
| `P(return > 0)` | phân loại nhị phân | khai báo theo model |
| `P(return > 5%)` | phân loại nhị phân | khai báo theo model |
| `P(return > 10%)` | phân loại nhị phân | khai báo theo model |
| Lợi nhuận kỳ vọng | hồi quy | khai báo theo model |
| Biến động / Sụt giảm | hồi quy | khai báo theo model |

Chân trời hỗ trợ (§6): NGẮN (1–20 ngày giao dịch), TRUNG (1–6 tháng), DÀI (6–36 tháng).

Mọi dự báo **phải** khai báo chân trời — không dự báo "không khung thời gian" (§6).

---

# 3. Tập dữ liệu đặc trưng

```text
features (kho đặc trưng, src/quant)              → ma trận X
targets (lợi nhuận tiến với chân trời khai báo)  → y
metadata (trade_date, stock_id, regime)          → định danh mẫu
```

- Phiên bản hóa đặc trưng: `feature_version`; phiên bản hóa dataset: `training_data_version`.
- Căn as-of từng dòng chống rò rỉ (§17).
- Chế độ thị trường lưu như đặc trưng ngữ cảnh (§13).

---

# 4. Huấn luyện & Kiểm chứng

```text
Train → Validation → Test (chia theo thời gian, không xáo trộn xuyên thời gian)
   + tập giữ out-of-sample
   + walk-forward / tái huấn luyện lăn
```

## 4.1. Chỉ số (§15)

Phân loại: Accuracy, Precision, Recall, F1, ROC-AUC, Log Loss, Brier Score, Calibration.

Đầu tư: CAGR, Sharpe, Sortino, Calmar, MaxDD, Win Rate, Profit Factor, Turnover, Transaction Cost.

## 4.2. Hiệu chuẩn (Calibration)

Output xác suất phải được hiệu chuẩn (Platt/isotonic). Model có xác suất lệch hiệu chuẩn thì không deploy được — độ tin cậy lái hành vi agent (§24).

---

# 5. Registry Model (§40)

`model_registry` yêu cầu: model_id, version, phiên bản dữ liệu huấn luyện, phiên bản đặc trưng, kỳ train/validation/test, chỉ số, tham số, chủ sở hữu, trạng thái.

Vòng đời trạng thái: `EXPERIMENTAL → VALIDATING → APPROVED → PRODUCTION → DEPRECATED`.

---

# 6. Lưu trữ & Đánh giá dự báo (§26)

- `predictions` lưu `(stock, trade_date, model_id, model_version, feature_version, target, predicted_value, horizon_days)`.
- Khi hết chân trời, `prediction_evaluations` ghi kết quả thực, sai số, hit.
- Hiệu quả model tính từ dự báo đã đánh giá — khép vòng lặp.

---

# 7. Tái lập được

```text
(stock, trade_date, data_version, feature_version, model_id, model_version)
   → dự báo tái lập được
```

Được đỡ bởi phiên bản hóa gần-như-bất biến ở mọi tầng (xem DATA_ARCHITECTURE.md §6).

---

# 8. Phản mẫu (Anti-Patterns)

- ❌ Train/tune trên kỳ test.
- ❌ Đặc trưng phân loại/ID rò rỉ thông tin tương lai (rò rỉ mục tiêu qua báo cáo điều chỉnh sau).
- ❌ Dùng LLM sinh đặc trưng/con số (§4.2, §47).
- ❌ Đưa model chưa đăng ký hoặc `EXPERIMENTAL` lên output production.
