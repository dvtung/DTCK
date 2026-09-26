# QUANT ENGINE — ĐỘNG CƠ ĐỊNH LƯỢNG (Bản tiếng Việt)

## Nền tảng Nghiên cứu & Quyết định Đầu tư AI

> Thuật ngữ chuyên môn (tên bảng, API, mã nguồn) giữ nguyên tiếng Anh.

**Phiên bản:** 1.0
**Trạng thái:** Cơ sở — suy ra từ SYSTEM_SPECIFICATION.md v1.0 (§11, §12, §13)

---

# 1. Tôn chỉ

Quant Engine **hoàn toàn tất định** và vận hành **không dính dáng LLM** (§4.2, §11).

- Mọi phép tính là Python thuần + NumPy/Pandas.
- Mọi công thức kiểm thử đơn vị với **giá trị kỳ vọng** (§38).
- LLM không bao giờ dùng cho: RSI, MA, P/E, lợi nhuận, biến động, xếp hạng, v.v. (§47 kiểm soát chi phí).

---

# 2. Module hệ số

## 2.1. Kỹ thuật (§11.1) — `src/market/technical/`

| Chỉ báo | Ghi chú |
|---|---|
| SMA / EMA | kỳ tùy chỉnh |
| RSI (14) | làm mượt Wilder |
| MACD | 12/26/9 |
| Bollinger Bands | 20, 2σ |
| ATR | 14 |
| ADX | 14 |
| Chỉ báo khối lượng | OBV, SMA khối lượng / mở rộng |
| Sức mạnh tương đối | vs chỉ số & phân vị vs universe |

## 2.2. Cơ bản (§11.2) — `src/market/fundamental/`

| Hệ số | Định nghĩa |
|---|---|
| Tăng trưởng doanh thu | YoY từ `financial_statements` |
| Tăng trưởng EPS | YoY |
| ROE | lợi nhuận ròng / vốn chủ |
| ROA | lợi nhuận ròng / tài sản |
| Biên | gộp / hoạt động / ròng |
| Nợ | D/E, khả năng trả lãi |
| Dòng tiền | OCF, FCF, biên FCF |
| Chất lượng | hợp chất chất lượng lợi nhuận (proxy dồn tích) |

## 2.3. Định giá (§11.3) — `src/market/valuation/`

So công ty vs ngành vs lịch sử (§11.3):

- P/E, Forward P/E, P/B, EV/EBITDA, EV/Sales, Dividend Yield, PEG → `valuation_daily`
- Phân vị trong ngành + phân vị vs lịch sử 5 năm của chính nó → góp vào `valuation_score`

## 2.4. Động lượng (§11.4) — `src/market/momentum/`

- Lợi nhuận 5D / 20D / 60D / 120D
- Sức mạnh tương đối (vs VNINDEX, vs universe)
- Mở rộng khối lượng

## 2.5. Rủi ro (§11.5) — `src/market/risk/`

- Biến động (năm hóa, EWMA)
- Beta (theo chỉ số universe)
- Sụt giảm tối đa trailing
- Thanh khoản (giá trị giao dịch bình quân pro-rata ADV/float)
- Rủi ro gap (tần suất gap mở cửa)
- Rủi ro lợi nhuận (biến động hàm ý ngày báo cáo)
- Rủi ro nợ (mức D/E)

---

# 3. Luồng chấm điểm (mỗi mã mỗi ngày)

```text
features (giá trị chỉ báo thô)
   ↓ lọc qua cổng chất lượng dữ liệu (§39)
hạng phân vị hệ số trong universe / ngành / lịch sử
   ↓
technical_score   (0-100)
fundamental_score (0-100)
valuation_score   (0-100)
momentum_score    (0-100)
quality_score     (0-100)
risk_score        (0-100)
   ↓
overall_score = Cơ bản×0.30 + Kỹ thuật×0.20 + Động lượng×0.15
              + Định giá×0.15 + Chất lượng×0.10 + Rủi ro×0.10      (§12 baseline)
   ↓
lưu vào factor_scores kèm scoring_version
```

> **Cảnh báo (đặc tả §12):** trọng số baseline là giả định cần backtest kiểm chứng/học lại — không bao giờ coi là tối ưu.

---

# 4. Quy tắc chuẩn hóa điểm

- Điểm chặn **0–100**.
- Hạng phân vị trong **universe hiện tại** (MVP: VN30), nên điểm là tương đối, không tuyệt đối.
- `market_regime` (từ Market Regime Engine §13) lưu kèm mỗi điểm như **đặc trưng ngữ cảnh** — có thể điều tiết xếp hạng/đặc trưng ML, không sửa điểm thô.
- Mỗi điểm phải giữ **vết phân rã** để giải thích (§43): tổng → điểm hệ số → chỉ báo con.

---

# 5. Market Regime Engine (§13)

Đầu vào: xu hướng VNINDEX, độ rộng thị trường, khối lượng, biến động (kiểu VIX), khối ngoại, lãi suất, thanh khoản, xoay vòng ngành.

Đầu ra: `{ "regime": "BULL|SIDEWAYS|BEAR|HIGH_VOLATILITY|CRISIS", "confidence": 0..1 }` lưu trong `market_regimes`.

Dùng làm đặc trưng ngữ cảnh cho: xếp hạng mã, dự báo ML, dựng danh mục, đánh giá rủi ro.

---

# 6. Trọng số chấm điểm (Baseline)

```text
Cơ bản         30%
Kỹ thuật       20%
Động lượng     15%
Định giá       15%
Chất lượng     10%
Rủi ro         10%
```

Phiên bản hóa `scoring_version = baseline_1.0`. Bộ trọng số khác là phiên bản mới, so sánh song song qua backtest.

---

# 7. Giải thích được (§43)

Mỗi điểm lưu đủ phân rã để khoan sâu:

```text
FPT Overall Score: 86
  Cơ bản:      92  → Tăng trưởng DT | Tăng trưởng EPS | ROE | Biên | FCF | Nợ
  Kỹ thuật:    84  → RSI | MACD | Xu hướng | Khối lượng
  Động lượng:  88  → 5D / 20D / 60D / 120D | Sức mạnh tương đối
  Định giá:    76  → P/E vs Ngành | P/B | EV/EBITDA
  Chất lượng:  91  → ...
  Rủi ro:      73  → Biến động | Beta | MaxDD | Thanh khoản
```

Hợp đồng phân rã (`src/quant/scoring/engine.py`): khi thiếu điểm hệ số thì các trọng số
còn lại được **chuẩn hóa lại**, và mọi đóng góp báo cáo dùng trọng số đã chuẩn hóa, nên
`Σ weighted_score == overall_score` và `Σ contribution_pct == 1` (cổ phần cộng đủ 100% điểm).
`weight` vì vậy là trọng số *áp dụng*, không phải baseline thô trong `scoring_weights.yaml`.

---

# 8. Yêu cầu kiểm thử (§38)

- Công thức chỉ báo đối chiếu giá trị tính tay.
- Luồng điểm kiểm: chặn (0–100), đơn điệu sắp xếp, toán trọng số, xử lý rỗng/NaN, biên dữ liệu tối thiểu (30 bar).
- Test hồi quy ghim trên dataset fixture đã commit.
