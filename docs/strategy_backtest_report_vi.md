# Báo cáo Backtest — Module chấm điểm 3 chiến lược (GĐ 5)

**Ngày chạy:** 2026-10-03 · **Dữ liệu:** `prices` thật (VN30) + `financial_statements` (CafeF) + `corporate_events` (Yahoo)
**Cửa sổ:** 2025-10-01 → 2026-09-30 · **Vũ trụ:** 30 mã VN30 · **Rebalance:** 21 phiên · **Top-N:** 5 · **Chi phí:** mặc định `ExecutionCosts` (15 bps hoa hồng + 5 bps trượt giá)

Lệnh tái lập:

```bash
python -m apps.worker.cli backtest-strategy --profile <short|mid|long> \
  --top-n 5 --rebalance-days 21 --start 2025-10-01 --end 2026-09-30 \
  --symbols ACB,BCM,BID,BVH,CTG,FPT,GAS,GVR,HDB,HPG,MBB,MSN,MWG,NVL,PLX,PNJ,POW,SAB,SHB,SSI,STB,TCB,TPB,VCB,VHM,VIC,VJC,VNM,VPB,VRE
```

---

## 1. Kết quả (FACT — số đo thật)

| Chỉ số | short | mid | long | **VNINDEX (mua & giữ)** |
|---|---|---|---|---|
| Tổng lợi nhuận | **−15.22%** | **−17.09%** | **−14.44%** | **+6.22%** |
| CAGR | −15.50% | −17.41% | −14.71% | +6.35% |
| Sharpe | −0.43 | **−0.66** | −0.56 | **+0.40** |
| Sortino | −0.42 | −0.65 | −0.53 | +0.38 |
| Max drawdown | **−35.97%** | −24.48% | −32.73% | **−16.38%** |
| Tỷ lệ thắng | 50.91% | 43.48% | 42.50% | — |
| Profit factor | 0.75 | 0.64 | 0.63 | — |
| Vòng quay/năm | **17.48×** | 13.52× | 9.84× | 0× |
| Chi phí giao dịch (VND/1 tỷ) | 34.969 | — | 19.678 | 0 |

> **Kết luận trung thực: cả 3 hồ sơ đều THUA VNINDEX trong cửa sổ này.** Trọng số hiện tại là *baseline khởi điểm* — đúng như cảnh báo đã ghi từ GĐ 1 (`configs/strategy_weights.yaml`: "phải tinh chỉnh qua backtest"). Báo cáo này là bằng chứng cho việc đó.

## 2. Vì sao thua — phân tích

1. **Vòng quay quá cao (13–17×/năm).** Rebalance 21 phiên + top-5 trên 30 mã ⇒ danh mục đổi gần như hoàn toàn mỗi lần. Chi phí 20 bps/lượt × 13–17 lượt ≈ **2.6–3.5%/năm** bào mòn, cộng thêm trượt giá thực tế.
2. **Chấm điểm theo phân vị vũ trụ** ⇒ trong thị trường đi ngang/giảm, hệ thống vẫn luôn chọn ra "5 mã đẹp nhất" trong một rổ đang giảm — không có cơ chế **đứng ngoài thị trường**.
3. **Cửa sổ 2025-10 → 2026-09:** VNINDEX +6.2% nhưng VN30 phân hoá mạnh; top-N theo điểm nhân tố không bắt được nhóm dẫn dắt.
4. **`published_at` = NULL** ⇒ BCTC bị trễ theo mốc pháp lý 45/90 ngày → nhóm growth/quality phản ánh dữ liệu cũ hơn thực tế đã công bố (hướng an toàn, nhưng làm tín hiệu chậm).
5. **Nhóm `macro` gần như trơ:** chỉ có `catalyst_event_ttm` (cổ tức/tách), phần lớn mã trùng giá trị ⇒ đóng góp thấp.
6. **`governance` thiếu dữ liệu:** `redflag_free` luôn `None` (chưa có ý kiến kiểm toán / số năm lỗ / OCF năm) ⇒ nhóm này chỉ còn 2 chỉ số đòn bẩy.

## 3. Đề xuất tinh chỉnh (theo thứ tự ưu tiên)

| # | Đề xuất | Kỳ vọng | Cách làm |
|---|---|---|---|
| 1 | **Cổng chế độ thị trường**: chỉ nắm giữ khi `VNINDEX > SMA50` | Cắt drawdown & tránh giai đoạn giảm | Thêm điều kiện vào `build_strategy` (đã có `data.benchmark`) |
| 2 | **Giảm vòng quay**: rebalance 63 phiên (quý) và/hoặc **vùng đệm top-N** (giữ mã đang nắm khi vẫn trong top 10) | Giảm chi phí 3–5× | Tham số hoá `rebalance_days` + thêm `buffer_n` |
| 3 | **Walk-forward tinh chỉnh trọng số** (`src/backtesting/walkforward.py`) trên 2020–2024, kiểm định 2025–2026 | Tránh quá khớp | Script `tune-weights` ghi ra `configs/strategy_weights.yaml` phiên bản mới |
| 4 | **Bổ sung dữ liệu còn thiếu**: ý kiến kiểm toán, số năm lỗ, OCF năm, khối ngoại | Nhóm `governance`/`moneyflow` có tín hiệu thật | Nguồn: CafeF/báo cáo kiểm toán; khối ngoại chưa có nguồn reachable |
| 5 | **Mở rộng vũ trụ VN100** (GĐ 6) | Tăng độ phân hoá top-N | `is_vn100` đã có trong `stocks` |
| 6 | **Kiểm chứng đa cửa sổ** (2020–2024, 2022 bear, 2023–2024 bull) trước khi kết luận | Tránh kết luận từ một cửa sổ | Chạy lại lệnh với `--start/--end` khác |

**Không** khuyến nghị bật module này cho tín hiệu thật ở trạng thái hiện tại — đúng tinh thần §3 (tham khảo, không phải khuyến nghị đầu tư) và ADR-007 (backtest trước khi phát tín hiệu).

## 4. Hạn chế của chính báo cáo

- Một cửa sổ 12 tháng, 30 mã — chưa đủ để kết luận thống kê.
- Chưa mô hình hoá **thanh khoản** (khối lượng khớp tối đa) và **giá trần/sàn** của HOSE.
- Carry-forward cho ngày ngưng giao dịch (volume=0) là quy ước backtest, không phải dữ liệu thật.
- `transaction_cost` báo theo VND tuyệt đối trên vốn khởi điểm 1 tỷ.
