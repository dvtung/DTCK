# Bộ nhớ dự án — Bối cảnh dự án (Bản tiếng Việt)

## Nền tảng Nghiên cứu & Quyết định Đầu tư AI (DTCK)

> Thuật ngữ chuyên môn (tên bảng, biến môi trường, lệnh, đường dẫn) giữ nguyên tiếng Anh.

---

## 1. Chúng ta đang xây gì

Nền tảng nghiên cứu & hỗ trợ ra quyết định cho **thị trường chứng khoán Việt Nam** (HOSE / HNX / UPCOM), bắt đầu với universe VN30, có nhiệm vụ:

1. Thu thập & kiểm chứng dữ liệu thị trường, cơ bản, định giá, tin tức, vĩ mô và sự kiện doanh nghiệp.
2. Chạy phân tích định lượng tất định (kỹ thuật, cơ bản, định giá, động lượng, rủi ro).
3. Chấm điểm & xếp hạng cổ phiếu; backtest chiến lược trước khi được phát tín hiệu.
4. (Sau này) bổ sung bằng chứng RAG, dự đoán ML và nghiên cứu bằng tác tử AI chồng lên trên.

**Hệ thống KHÔNG phải là máy tự ra quyết định đầu tư.** Nó hỗ trợ con người: `AI Analysis → Risk Validation → Human Review → Investment Decision` (§4.6).

---

## 2. Phi mục tiêu (§3, luôn hiển thị)

- Không cam kết lợi nhuận; không dự đoán giá tuyệt đối; không thay thế chuyên gia đầu tư; không tự động giao dịch; không để LLM bịa số liệu tài chính; không để LLM tự đưa ra lệnh MUA/BÁN.

---

## 3. Triết lý lõi (đặc tả §56)

> **AI không thay thế phán đoán đầu tư. AI tăng tốc độ, tính nhất quán, chiều sâu và khả năng truy vết của nghiên cứu đầu tư.**

Luồng: `DATA → QUANT → BACKTEST → ML → RAG → AI AGENT → EVIDENCE → RISK CONTROL → HUMAN`

---

## 4. Nguyên tắc thiết kế ràng buộc (§4)

1. **Dữ liệu trước** — dữ liệu xấu ⇒ đặc trưng xấu ⇒ model xấu ⇒ agent xấu.
2. **Tính toán tất định trước** — RSI/P-E/ROE/… luôn do phần mềm tính, không bao giờ do LLM.
3. **LLM là tầng lập luận** — lập kế hoạch, chọn tool, tổng hợp; không bao giờ là nguồn chân lý.
4. **Lập luận dựa trên bằng chứng** — khẳng định → bằng chứng → nguồn → timestamp → phiên bản dữ liệu.
5. Backtest trước khi triển khai; con người trong vòng lặp; kiểm toán đầy đủ.

---

## 5. Con số then chốt

| Mục | Giá trị |
|---|---|
| Thị trường | Việt Nam (HOSE, HNX, UPCOM) |
| Universe khởi đầu | VN30 → VN100 → toàn thị trường |
| Khung thời gian | Ngắn 1–20 phiên, Trung 1–6 tháng, Dài 6–36 tháng |
| Trọng số chấm điểm cơ sở | Cơ bản 30 / Kỹ thuật 20 / Động lượng 15 / Định giá 15 / Chất lượng 10 / Rủi ro 10 |
| Mục tiêu hiệu năng API | P95 < 500 ms (không LLM) |

---

## 6. Kiến trúc trong một đoạn

FastAPI (API) + Streamlit (dashboard MVP) + Worker (scheduler/nạp dữ liệu) trên **PostgreSQL/TimescaleDB** (dữ liệu có cấu trúc, hypertable) + **Qdrant** (tìm kiếm vector). **Quant Engine** tất định sinh đặc trưng/điểm hệ số có phiên bản; **Backtesting Engine** kiểm chứng chiến lược; các giai đoạn sau bổ sung ML (XGBoost/LightGBM), RAG và tác tử LangGraph sau một tầng tool — LLM không bao giờ chạm trực tiếp CSDL và không bao giờ tự tính số.

Xem `docs/ARCHITECTURE_vi.md` để có bức tranh đầy đủ.

---

## 7. Tham chiếu chính

| Phân hệ / Nội dung | Đường dẫn tài liệu (100% tiếng Việt) |
|---|---|
| Đặc tả hệ thống | `docs/SYSTEM_SPECIFICATION.md` |
| Bản thảo ý tưởng | `docs/AI_INVESTMENT_CONCEPT.md` |
| Kiến trúc tổng thể | `docs/ARCHITECTURE_vi.md` |
| Kiến trúc dữ liệu | `docs/DATA_ARCHITECTURE_vi.md` |
| Lược đồ CSDL | `docs/DATABASE_SCHEMA_vi.md` |
| Quant engine | `docs/QUANT_ENGINE_vi.md` |
| Kiểm nghiệm backtesting | `docs/BACKTESTING_vi.md` |
| Học máy (ML) | `docs/ML_ARCHITECTURE_vi.md` |
| Truy xuất tri thức (RAG) | `docs/RAG_ARCHITECTURE_vi.md` |
| Tác tử AI (Agents) | `docs/AGENT_ARCHITECTURE_vi.md` |
| Đặc tả API REST | `docs/API_SPECIFICATION_vi.md` |
| Nguồn dữ liệu | `docs/DATA_SOURCES_vi.md` |
| Triển khai & Vận hành | `docs/DEPLOYMENT_vi.md` |
| An toàn & Bảo mật | `docs/SECURITY_vi.md` |
| Hướng dẫn vận hành | `helper/deployment_vi.md` · `helper/resources_vi.md` |
| Trang HTML báo cáo | `docs/index.html`, `status.html`, `structure.html`, `modules.html`, `database.html`, `pipeline.html`, `api.html` |
| Quy ước ngôn ngữ tài liệu | **Từ nay toàn bộ tài liệu markdown của dự án chỉ sử dụng tiếng Việt và các file tiếng Việt.** |
| Quy ước cập nhật HTML | **Chỉ cập nhật các file HTML (`docs/*.html`) khi người dùng yêu cầu trực tiếp để tiết kiệm token context.** |

