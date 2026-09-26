# KIẾN TRÚC TÁC TỬ AI (Bản tiếng Việt)

## Nền tảng Nghiên cứu & Quyết định Đầu tư AI

> Thuật ngữ chuyên môn (tên bảng, API, mã nguồn) giữ nguyên tiếng Anh.

**Phiên bản:** 1.0
**Trạng thái:** ĐÃ TRIỂN KHAI (T013, 2026-09-16) — tất định, offline, không LLM. Orchestrator giải task qua registry, dựng kế hoạch §21, gọi tool (ToolCatalog bọc MarketService/RagService), audit từng lượt chạy (§31), hỗ trợ retry/timeout/failure theo §45. LangGraph là hướng nâng cấp Phase-5 (§34) khi bật LLM; baseline hiện cố ý không LLM để thỏa cổng thứ tự đặc tả §57.

---

# 1. Khi nào Agent hành động (thứ tự quan trọng, đặc tả §57)

**Agent TẮT cho tới khi Data + Quant + Backtest đạt baseline kiểm chứng được (MVP-1).**

```text
MVP-1: data → quant → score → ranking → backtest → dashboard     (KHÔNG LLM)
MVP-2: + news/RAG/evidence + Analysis Agent
MVP-3: + ML prediction + market regime + Portfolio Agent + monitoring + alerts
```

---

# 2. Framework

- **LangGraph** dự kiến cho điều phối agent có trạng thái, kiểm soát được (§34) — hướng nâng cấp Phase-5 khi bật LLM. Baseline MVP-1/T013 dùng orchestrator tất định (không LLM) giải kế hoạch §21, gọi tool và ghi audit §31.
- **Trừu tượng hóa provider LLM** (ADR-005) — không khóa nhà cung cấp.
- Mọi output agent tuân **schema Pydantic** (ADR-006, §23).

---

# 3. Các agent (§20)

## 3.1. Research Agent (Nghiên cứu)
- Tìm thông tin, tổng hợp hồ sơ công ty, thu thập bằng chứng, nêu sự kiện quan trọng.
- Dùng nặng tool RAG + truy xuất tin tức/sự kiện doanh nghiệp.

## 3.2. Analysis Agent (Phân tích)
- Phân tích một mã: gọi Quant Tool, RAG Tool, tổng hợp bằng chứng → dựng luận điểm đầu tư.
- Sinh `InvestmentAnalysis` (§23) gồm điểm, luận điểm, chất xúc tác, rủi ro, điều kiện vô hiệu, độ tin cậy, bằng chứng.

## 3.3. Monitoring Agent (Giám sát)
- Theo dõi biến động giá/khối lượng/tin/sự kiện/cơ bản/rủi ro.
- Phát cảnh báo khi: đổi tín hiệu, tăng rủi ro, tin quan trọng, bứt phá kỹ thuật, suy yếu cơ bản (§20.3).

## 3.4. Portfolio Agent (Danh mục)
- Cỡ vị thế, tương quan, độ phủ ngành, rủi ro danh mục, tập trung, sụt giảm, ngân sách rủi ro (§20.4, §27).
- Quyết định danh mục **tách biệt** với xếp hạng mã (§27).

## 3.5. Orchestrator (§21)
- Điều phối trung tâm. Ví dụ kế hoạch cho "Phân tích FPT":

```text
1. Chế độ thị trường   6. So sánh cùng ngành   10. Dự báo ML
2. Giá                 7. Tin tức              11. Luận điểm đầu tư
3. Kỹ thuật            8. Sự kiện doanh nghiệp
4. Cơ bản              9. Rủi ro               (+ bằng chứng)
5. Định giá
```

---

# 4. Kiến trúc Tool (§22)

LLM → Gọi tool → Dịch vụ ứng dụng → (DB / Quant Engine / RAG) → Kết quả có cấu trúc → LLM.

**LLM không bao giờ chạm trực tiếp vào CSDL.**

Danh mục tool (MVP): `get_stock_price`, `get_technical`, `get_fundamentals`, `get_valuation`, `get_peer_analysis`, `get_market_regime`, `get_news`, `get_corporate_events`, `get_prediction`, `get_risk`.

---

# 5. Output có cấu trúc (§23)

```python
class InvestmentAnalysis(BaseModel):
    symbol: str
    overall_score: float
    market_regime: str
    technical_score: float
    fundamental_score: float
    valuation_score: float
    momentum_score: float
    risk_score: float
    thesis: str
    catalysts: list[str]
    risks: list[str]
    invalidation_conditions: list[str]
    confidence: float
    evidence: list[Evidence]
```

---

# 6. Mô hình độ tin cậy (§24)

Độ tin cậy kết hợp: hiệu chuẩn model, chất lượng dữ liệu, đồng thuận tín hiệu, chế độ thị trường + **(tùy chọn) đồng thuận agent**. Luôn điều chỉnh rủi ro bằng guardrail (§42).

---

# 7. Audit & Quản trị

- Mỗi lượt chạy → `agent_runs` (yêu cầu user, agent, model/phiên bản, prompt, output cuối, độ trễ, token) (§31).
- Mỗi tool call → `agent_tool_calls` (tool, input, output) (§22).
- Registry agent → `agent_registry` (phiên bản, phiên bản prompt, tool, dữ liệu cho phép, schema output, điểm đánh giá, trạng thái) (§41).

**Agent BỊ CẤM (§41):** đổi schema DB, đổi model, đổi trọng số chấm điểm, thực hiện giao dịch, xóa audit log.

---

# 8. Guardrail LLM (§4.3, §47)

- LLM **không bao giờ** tự tính RSI/P/E/MA/lợi nhuận/biến động/xếp hạng — chỉ lấy từ tool.
- LLM **không bao giờ** bịa số liệu tài chính (đặc tả §3 phi mục tiêu).
- Output phải validate theo schema; output sai → retry với fallback → failure.
- Timeout + retry + fallback là bắt buộc khi chạy agent (§45).

---

# 9. Định nghĩa MVP-2 (§50)

User hỏi "Phân tích FPT" → hệ thống trả Phân tích định lượng + Phân tích tin tức + Luận điểm đầu tư + Rủi ro + Bằng chứng.
