# PROMPT CHO CLINE: Xây dựng module "Chấm điểm & Gợi ý cổ phiếu đa chiến lược"

> Cách dùng: dán toàn bộ nội dung từ mục "VAI TRÒ" trở xuống vào Cline (chế độ **Plan** trước, sau khi duyệt kế hoạch mới chuyển sang **Act**).

---

## VAI TRÒ

Bạn là kỹ sư phần mềm cấp cao kiêm chuyên gia phân tích tài chính (20+ năm kinh nghiệm thị trường chứng khoán Việt Nam). Bạn đang làm việc trong một codebase **đã có sẵn** hệ thống đánh giá xu hướng cổ phiếu cho rổ VN30 và VN100.

## MỤC TIÊU

Thêm một **module/function mới** vào hệ thống hiện có: **Chấm điểm đa yếu tố và gợi ý đầu tư theo 3 chiến lược** (ngắn hạn/lướt sóng, trung hạn, dài hạn) cho các mã trong VN30/VN100. Module phải **tái sử dụng** dữ liệu, chỉ báo xu hướng và hạ tầng sẵn có, không viết lại những gì đã tồn tại.

## BƯỚC 0 – KHÁM PHÁ CODEBASE (bắt buộc, làm trước khi viết code)

1. Đọc cấu trúc thư mục, README, file cấu hình, file phụ thuộc (requirements/pyproject/package.json).
2. Xác định và tóm tắt lại cho tôi:
   - Ngôn ngữ, framework, kiểu lưu trữ dữ liệu (DB/file), cách lập lịch chạy.
   - Nguồn dữ liệu giá/khối lượng hiện dùng; có dữ liệu báo cáo tài chính chưa.
   - Các chỉ báo xu hướng đã có, định dạng đầu ra hiện tại, cách hiển thị (API/UI/báo cáo).
   - Quy ước đặt tên, cách viết test, cách ghi log.
3. Liệt kê những phần **có thể tái sử dụng** và những phần **còn thiếu**.
4. **Đưa ra kế hoạch chi tiết và dừng lại chờ tôi duyệt.** Nếu có điểm không rõ, hỏi tôi tối đa 5 câu hỏi gộp trong một lần.

## NGUYÊN TẮC BẮT BUỘC

- Tuân theo kiến trúc và quy ước của codebase hiện tại; không đổi công nghệ nếu không có lý do chính đáng.
- Module mới tách biệt rõ ràng (ví dụ thư mục `scoring/` hoặc tên phù hợp với cấu trúc hiện có), kết nối với hệ thống cũ qua giao diện/hàm rõ ràng.
- **Không phá vỡ chức năng hiện có.** Mọi thay đổi trên file cũ phải tối thiểu và có test.
- **Không viết cứng** trọng số, ngưỡng, danh sách mã: đặt trong file cấu hình (YAML/JSON).
- **Không bịa dữ liệu.** Nếu thiếu dữ liệu, trả về `null` kèm cờ chất lượng dữ liệu, không giả định giá trị.
- **Tránh nhìn trước tương lai (look-ahead bias):** dữ liệu tài chính chỉ được dùng từ **ngày công bố** trở đi.
- Không đưa khóa API/mật khẩu vào mã nguồn; dùng biến môi trường.
- Mỗi giai đoạn: viết code, viết test, chạy test, báo kết quả rồi mới sang giai đoạn tiếp theo.

## KIẾN TRÚC MỤC TIÊU

```
[Nguồn dữ liệu] → [ETL] → [Kho dữ liệu] → [Feature Engine]
   → [Bộ lọc loại trừ] → [Chấm điểm đa yếu tố] → [Gợi ý & Giải thích]
   → [API / Giao diện / Cảnh báo]
        ↑ [Backtest & Giám sát chất lượng] (xuyên suốt)
```

### 1. Nguồn dữ liệu và ETL
- Giá, khối lượng (đã điều chỉnh theo cổ phiếu thưởng, chia tách, cổ tức), dòng tiền khối ngoại/tự doanh.
- Báo cáo tài chính theo quý kèm **ngày công bố**; sự kiện doanh nghiệp (cổ tức, tăng vốn, phát hành).
- Dữ liệu vĩ mô cơ bản (lãi suất, tỷ giá, tăng trưởng tín dụng) và mã ngành.
- Dùng lại bộ thu thập hiện có; chỉ thêm adapter cho nguồn còn thiếu. Mỗi nguồn là một adapter độc lập, có retry, log và kiểm tra chất lượng (thiếu, trễ, giá trị bất thường).

### 2. Kho dữ liệu
Thêm các bảng/collection (đổi tên theo quy ước hiện có, kèm migration):
`securities`, `prices_daily`, `financials_quarterly` (có `published_at`), `corporate_actions`, `macro`, `features` (mã, ngày, tên chỉ số, giá trị), `scores` (mã, ngày, chiến lược, điểm tổng, điểm từng nhóm), `signals` (xếp hạng, vùng mua, cắt lỗ, mục tiêu, lý do, độ tin cậy).

### 3. Feature Engine
Mỗi chỉ số là một hàm thuần, có kiểm thử, đăng ký trong một registry:
- **Tăng trưởng:** doanh thu, LNST, EPS (YoY theo quý, CAGR 3–5 năm).
- **Chất lượng:** ROE, ROA, ROIC, biên gộp/ròng, CFO/LNST, vòng quay tồn kho/phải thu.
- **An toàn tài chính:** nợ/vốn chủ, khả năng trả lãi, thanh toán hiện hành.
- **Định giá:** P/E, P/B, P/S, EV/EBITDA, PEG; so với lịch sử của chính mã và với trung vị ngành.
- **Kỹ thuật:** MA20/50/200, RSI, MACD, ATR, độ mạnh tương đối so với VN-Index và ngành, đột phá nền giá, khối lượng. **Tái sử dụng chỉ báo xu hướng đang có.**
- **Dòng tiền và thanh khoản:** khối ngoại ròng, GTGD trung bình, tỷ lệ khối lượng so với trung bình.
- **Catalyst và rủi ro:** tăng vốn pha loãng, cổ đông lớn bán ra, cảnh báo/kiểm soát/hạn chế giao dịch, ý kiến kiểm toán.
- **Chuẩn hóa theo ngành:** quy đổi sang xếp hạng phân vị trong ngành (0–100). Bộ chỉ số **riêng** cho ngân hàng (NIM, CASA, NPL, bao phủ nợ xấu, CAR, tăng trưởng tín dụng), bất động sản (nợ vay, tiền khách ứng trước, backlog bàn giao, quỹ đất), chứng khoán (margin, tự doanh, thanh khoản thị trường). Không áp bộ chỉ số nợ/định giá chung cho các ngành này.

### 4. Bộ lọc loại trừ (red flag)
Loại hoặc gắn cờ cảnh báo mã khi: bị cảnh báo/kiểm soát/hạn chế giao dịch; kiểm toán từ chối/ngoại trừ; thanh khoản dưới ngưỡng; lỗ kéo dài kèm dòng tiền kinh doanh âm; nợ vượt ngưỡng của ngành. Mọi ngưỡng đặt trong cấu hình.

### 5. Chấm điểm đa yếu tố (0–100) theo 3 hồ sơ chiến lược
Trọng số khởi điểm (đọc từ cấu hình, sẽ tinh chỉnh bằng backtest):

| Nhóm điểm | Ngắn hạn | Trung hạn | Dài hạn |
|---|---|---|---|
| Kỹ thuật / xu hướng / RS | 40% | 20% | 5% |
| Dòng tiền & thanh khoản | 25% | 10% | 5% |
| Tăng trưởng | 10% | 30% | 20% |
| Chất lượng doanh nghiệp | 5% | 15% | 30% |
| Định giá | 5% | 15% | 25% |
| Vĩ mô / ngành / catalyst | 15% | 10% | 5% |
| Quản trị & rủi ro | 0% | 0% | 10% |

Khi một nhóm thiếu dữ liệu: tính lại trọng số trên các nhóm còn lại và hạ **độ tin cậy**, không điền giá trị giả.

### 6. Gợi ý và giải thích
Với mỗi mã và mỗi chiến lược, xuất:
- Xếp hạng A/B/C/D từ điểm tổng và quy tắc (ví dụ: ngắn hạn yêu cầu xu hướng tăng xác nhận).
- Vùng mua tham khảo, mức cắt lỗ (dựa ATR/đáy quan trọng), mục tiêu, tỷ lệ lời/lỗ.
- Danh sách lý do chính, rủi ro chính, độ tin cậy.
- **Lớp giải thích:** đóng góp của từng nhóm chỉ số vào điểm tổng để người dùng hiểu "vì sao".
- Luôn kèm câu miễn trừ trách nhiệm: kết quả chỉ mang tính tham khảo, không phải khuyến nghị đầu tư cá nhân.

### 7. Phân phối
- Mở rộng API hiện có với các endpoint: lấy điểm theo mã, bảng xếp hạng theo chiến lược, sàng lọc theo điều kiện, lịch sử điểm, giải thích điểm.
- Giao diện: bảng sàng lọc, trang chi tiết mã (điểm theo nhóm, biểu đồ lịch sử điểm, gợi ý). Làm theo UI hiện có nếu đã có.
- Cảnh báo (email/Telegram, tùy hạ tầng hiện có) khi xếp hạng hoặc tín hiệu thay đổi.
- Lập lịch chạy hằng ngày sau khi đóng cửa; chạy lại theo quý khi có báo cáo tài chính mới.

### 8. Backtest và giám sát
- Backtest theo từng thời điểm quá khứ với dữ liệu "tại thời điểm đó", có phí giao dịch, trượt giá, ràng buộc thanh khoản.
- Báo cáo: tỷ lệ thắng, lợi nhuận/lỗ trung bình, mức sụt giảm tối đa, Sharpe, so với VN-Index và so với hệ thống xu hướng hiện tại.
- Tách dữ liệu huấn luyện/kiểm định (ví dụ walk-forward) để tránh quá khớp khi tinh chỉnh trọng số.
- Giám sát: kiểm tra chất lượng dữ liệu hằng ngày, log các lần chạy, theo dõi hiệu quả gợi ý thực tế.

## LỘ TRÌNH TRIỂN KHAI (làm tuần tự, mỗi giai đoạn có tiêu chí nghiệm thu)

| GĐ | Nội dung | Nghiệm thu |
|---|---|---|
| 1 | Khám phá codebase, kế hoạch chi tiết, cấu hình, schema và migration | Tôi duyệt kế hoạch; migration chạy được |
| 2 | ETL cho dữ liệu còn thiếu (báo cáo tài chính có `published_at`, sự kiện doanh nghiệp), kiểm tra chất lượng | Dữ liệu VN30 nạp đầy đủ, test qua |
| 3 | Feature Engine + chuẩn hóa theo ngành, ưu tiên hồ sơ **trung hạn** | Chỉ số tính đúng trên mẫu kiểm tra thủ công |
| 4 | Bộ lọc loại trừ + chấm điểm 3 chiến lược + gợi ý + giải thích | Bảng xếp hạng VN30 xuất được, mỗi điểm có giải thích |
| 5 | Backtest và báo cáo hiệu quả | Báo cáo so với hệ thống hiện tại |
| 6 | API, giao diện, cảnh báo, mở rộng sang VN100 | Endpoint có test, tài liệu cập nhật |

Bắt đầu với VN30 và hồ sơ trung hạn, sau đó mở rộng.

## YÊU CẦU CHẤT LƯỢNG

- Test đơn vị cho từng chỉ số và hàm chấm điểm; test tích hợp cho luồng ETL → điểm → gợi ý; test hồi quy bảo đảm chức năng cũ không đổi.
- Type hints/docstring theo quy ước dự án; log có cấu trúc.
- Cập nhật README: cách cấu hình trọng số, cách chạy ETL, chấm điểm, backtest.
- Mỗi giai đoạn kết thúc bằng báo cáo ngắn: đã làm gì, file nào thay đổi, kết quả test, rủi ro còn lại, đề xuất bước tiếp.

## ĐẦU RA MONG ĐỢI

1. Tóm tắt khám phá codebase và kế hoạch chi tiết (chờ duyệt).
2. Code module, migration, cấu hình YAML mẫu, test.
3. Tài liệu hướng dẫn sử dụng và vận hành.
4. Báo cáo backtest và đề xuất tinh chỉnh trọng số.

**Bắt đầu ngay với BƯỚC 0. Không viết code cho đến khi tôi duyệt kế hoạch.**
