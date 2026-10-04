# THIẾT KẾ NGUỒN DỮ LIỆU (Bản tiếng Việt)

## Nền tảng Nghiên cứu & Quyết định Đầu tư AI

> Thuật ngữ chuyên môn (tên bảng, API, mã nguồn) giữ nguyên tiếng Anh.

**Phiên bản:** 1.1
**Trạng thái:** Cơ sở (T002) — nhà cung cấp ứng viên, lựa chọn & kế hoạch credential.
**Phạm vi:** Thị trường chứng khoán Việt Nam (HOSE / HNX / UPCOM), universe khởi đầu VN30.
**Kho chính:** PostgreSQL + TimescaleDB (xem `docs/DATABASE_SCHEMA.md`).

> ⚠️ **Trung thực kiểm chứng:** egress mạng **không có** khi viết tài liệu này,
> nên URL endpoint, hình thù response và giới hạn tần suất từng provider
> đánh dấu **`TO VERIFY`** và phải xác nhận trước ở T004. Sự *tồn tại*,
> mô hình cấp phép và năng lực chung của provider là sự thật công khai đã biết.

> Cập nhật 2026-09-25: `yahoo` (EOD) và `cafef` (RSS) đã **kiểm chứng trực tiếp**
> (`VERIFIED_2026-09-25` trong `configs/sources.yaml`); E2E `fetched=62 written=62 quality=94.88`.

> Cập nhật 2026-09-27: **`ssix_finipro` (SSI FastConnect) đã kiểm chứng trực tiếp**
> bằng credential consumer live → trở thành nguồn **chính** cho thị trường
> (`Market/DailyOhlc`: 68 dòng cho FPT,VCB,HPG,ACB · quality 93.74;
> `Market/DailyIndex`: 34 dòng cho VNINDEX,VN30). Job nạp EOD 11:30/15:30 tự chạy chuỗi
> `ssix_finipro → yahoo → vndirect → tcbs → dsc` (`market_provider_chain`).

---

# 1. Mục tiêu & Phi mục tiêu

## Mục tiêu
- Phủ mọi miền trong `docs/DATA_ARCHITECTURE.md` §1 (thị trường, cơ bản,
  định giá, vĩ mô, sự kiện doanh nghiệp, tin tức) với **một nguồn chính và ít nhất một
  dự phòng**.
- Ưu tiên nguồn **miễn phí / chính thức**; dành nguồn trả phí cho lỗ hổng hẹp.
- Mọi nguồn nằm sau **trừu tượng hóa provider** nhỏ để đổi vendor
  không bao giờ chạm code pipeline/DB (gợi ADR-005 quyết định trừu tượng hóa LLM).
- Credential **không bao giờ** trong code/Git/image (đặc tả §32, `docs/SECURITY.md`).

## Phi mục tiêu
- Không dữ liệu intraday/tick ở Phase 1 (chỉ EOD; intraday sau).
- Không mua terminal thương mại (Bloomberg/Refinitiv) trong MVP.
- **Không** dựa vào một API không chính thức duy nhất làm nguồn đơn lẻ.
# 4. Danh mục provider (rút gọn — đủ xem trong `configs/sources.yaml`)

| Nguồn | Vai trò | Trạng thái 2026-09-27 |
|---|---|---|
| `ssix_finipro` (SSI FastConnect) | chính thị trường (+ tin) | **kiểm chứng 2026-09-27** (consumer credential live): `Market/AccessToken` (JWT, cache + refresh khi 401), `Market/DailyOhlc` (68 dòng · quality 93.74), `Market/DailyIndex` (34 dòng) — KI-006/KI-007 đã đóng phần thị trường. **KHÔNG có endpoint báo cáo tài chính** (xem mục 8.1) |
| `cafef_financials` (CafeF apiweb) | **cơ bản** — BCTC quý/năm (CĐKT, KQKD, LCTT) | **kiểm chứng 2026-10-03**: cả 3 endpoint trả `200` với dữ liệu FPT thật (snapshot: `tests/fixtures/cafef_financials_sample.json`); nạp live VN30 → `financial_statements` có dữ liệu thật. Lưu ý: CafeF **không** trả ngày công bố ⇒ `published_at = NULL`; một số chỉ tiêu LCTT có giá trị rác (vượt `Numeric(24,4)`) → bị gắn cờ + bỏ |
| `vndirect_financials` (VNDirect finfo) | cơ bản + sự kiện DN (dự phòng) | provider `VNDirectFinancialProvider` (mapping phòng thủ); **chưa kiểm chứng live** — `finfo-api.vndirect.com.vn` timeout từ host dev → `MAPPING_TO_VERIFY_2026-10-03` |
| `yahoo` | dự phòng thị trường — EOD OHLCV mã `.VN` (anonymous) | **kiểm chứng 2026-09-25**: un-adjust tách qua `events=split`, `trading_value` ≈ close×volume, bỏ dòng volume 0 |
| `yahoo` (corporate actions) | **sự kiện doanh nghiệp** — cổ tức tiền mặt + tách cổ phiếu | **kiểm chứng 2026-10-03** (`events=div,split` trên cùng endpoint chart): nạp live VN30 → 238 dòng (154 DIVIDEND + 84 SPLIT), 2020-02→2026-10. `announced_date` = NULL (Yahoo không công bố ngày thông báo) |
| `imf_worldbank` (IMF datamapper) | **vĩ mô** — GDP growth + CPI inflation (năm) | **kiểm chứng 2026-10-03** (`/external/datamapper/api/v1/{code}/VNM` → 200): nạp live → 32 dòng (2010–2025). **Chỉ lưu năm đã kết thúc** — dự báo WEO không bao giờ được ghi. World Bank/GSO/SBV **không** reachable từ host dev (timeout/DNS/HTML) |
| `vndirect`, `tcbs`, `dsc` | dự phòng thị trường/cơ bản (anonymous, không chính thức) | đã chọn làm dự phòng (vndirect/tcbs unreachable từ host 2026-09-25) |
| `sbv`, `gso`, `imf_worldbank` | vĩ mô (công khai chính thức) | đã chọn |
| `cafef`, `vnexpress`, `vietstock_news` | tin tức Việt (RSS) | CaféF **kiểm chứng 2026-09-25** (parser stdlib, đã nạp 50 bài thật); còn lại đã chọn |
| `hose`, `hnx`, `vietstock`, `tradingeconomics`, `newsdata` | bổ sung chính thức/cấp phép/trả phí | **tắt** tới khi quyết cấp phép/chi phí |

---

# 4. Provider khuyến nghị theo miền (§4 bản Anh)

(Tóm tắt đầy đủ xem `configs/sources.yaml` — 16 provider / 11 bật.)

| Miền | Chính | Dự phòng | Ghi chú |
|---|---|---|---|
| Thị trường EOD | `ssix_finipro` | `yahoo` → `vndirect` → `tcbs` → `dsc` | `ssix_finipro` đã kiểm chứng 2026-09-27 (consumer credential); `yahoo` kiểm chứng 2026-09-25 (chart v8, anonymous) |
| Cơ bản | `cafef_financials` (CafeF apiweb) | `vndirect_financials` | **SSI không có endpoint BCTC** (danh sách hàm FastConnect Data xác nhận 2026-10-03; BCTC của SSI ở sản phẩm iExcel — không có REST API). CafeF `apiweb` **kiểm chứng 2026-10-03** (3 endpoint 200 + nạp live VN30); VNDirect finfo là dự phòng nhưng timeout từ host dev |
| Vĩ mô | `imf_worldbank` (IMF datamapper) | `gso` → `tradingeconomics` | **IMF kiểm chứng 2026-10-03** cho `GDP_GROWTH_PCT` + `CPI_INFLATION_PCT`; GSO không có DNS, TradingEconomics cần trả phí. Lãi suất/tăng trưởng tín dụng chưa có nguồn reachable |
| Sự kiện doanh nghiệp | `yahoo` (div/split) | `vndirect_financials` → `hose` → `cafef` | **Yahoo kiểm chứng 2026-10-03** (238 sự kiện VN30); `hose`/`hnx` chờ đọc cấp phép |
| Tin tức | `cafef` | `vnexpress` → `vietstock` | CaféF RSS đã kiểm chứng 2026-09-25 (50 bài thật) |

---

# 5. Ánh xạ Miền → Bảng (§5 bản Anh — nguồn nuôi gì)

| Miền | Bảng (`docs/DATABASE_SCHEMA.md`) | Provider |
|---|---|---|
| Thị trường | `prices`, `adjusted_prices`, `index_prices`, `foreign_flows`, `prop_trading_flows` | `ssix_finipro`, `vndirect`, `tcbs`, `dsc` (+ `yahoo` EOD đã kiểm chứng) |
| Cơ bản | `financial_statements`, `financial_ratios` | `ssix_finipro`, `vndirect`, `vietstock` |
| Định giá | `valuation_daily` | **tính** bởi Quant Engine (đối chiếu: `ssix_finipro`) |
| Vĩ mô | `macro_indicators` | `sbv`, `gso`, `imf_worldbank`, `tradingeconomics` |
| Sự kiện doanh nghiệp | `corporate_events` | `ssix_finipro`, `hose`, `cafef` |
| Tin tức | `news`, `news_symbols` | `cafef`, `vnexpress`, `vietstock`, `newsdata` |

---

# 6. Kế hoạch credential & secret (§6 bản Anh)

Theo `docs/SECURITY.md` §2 (không secret trong code/Git/image; chỉ env).

| Mục đích | Biến env (chỉ tên — trống trong `.env.example`) | Provider |
|---|---|---|
| Provider chính thị trường/cơ bản | `SSI_CONSUMER_ID` + `SSI_CONSUMER_SECRET` (đổi lấy JWT), hoặc `FINIPRO_ACCESS_TOKEN` (token cấp sẵn) | `ssix_finipro` |
| Base URL SSI FastConnect (tùy chọn) | `SSI_API_URL` (mặc định `https://fc-data.ssi.com.vn`) | `ssix_finipro` |
| API tin tức/từ khóa trả phí (tùy chọn) | `NEWS_API_KEY` | `newsdata` |
| Tổng hợp vĩ mô (tùy chọn, trả phí) | `TRADINGECONOMICS_API_KEY` | `tradingeconomics` |
| Chọn provider dữ liệu thị trường (lặp registry) | `MARKET_DATA_PROVIDER`, `MARKET_DATA_API_KEY` | chung |
| Chọn provider cơ bản | `FUNDAMENTAL_DATA_PROVIDER` | chung |
| Chọn provider tin | `NEWS_PROVIDER`, `NEWS_API_KEY` | chung |

Quy tắc:
- Mọi secret provider **tùy chọn**; provider anonymous chạy không key.
- `.env.example` chỉ ghi **tên với giá trị rỗng**.
- Vòng fetch dữ liệu của worker nằm trong Docker network riêng; chỉ host provider
  cụ thể được tới (egress whitelist, §32 / `docs/SECURITY.md` §7).
- Production: key bơm lúc deploy từ secret manager; không bao giờ bake.
# 7. Ma trận dự phòng / chuyển đổi (§7 bản Anh)

| Khi (chính) lỗi | Thì (chuỗi dự phòng) | Cổng |
|---|---|---|
| `ssix_finipro` thị trường | `yahoo` → `vndirect` → `tcbs` → `dsc` | kiểm chứng hoặc cổng điểm chất lượng |
| `ssix_finipro` cơ bản | `vndirect` → `vietstock` | report_date hợp lý |
| `sbv`/`gso` | `imf_worldbank` (+ `tradingeconomics` nếu có phép) | cửa sổ tươi |
| `cafef` | `vnexpress` → `vietstock` | khử trùng trên `(source,title)` |

Dự phòng **không lặng lẽ**: mỗi lần chuyển ghi vào `audit_logs` để provenance luôn tái lập được.

> **Thực thi lúc chạy (2026-09-27):** job EOD của worker không tự viết lại chuỗi
> trên mà đọc từ `configs/sources.yaml` qua `market_provider_chain(primary=...)`
> (`src/data/providers/registry.py`) — nguồn `SCHEDULER_EOD_SOURCE` (mặc định
> `ssix_finipro`) đứng đầu, sau đó `fallback_chains.market`. Nguyên tắc: nguồn
> không dựng được (thiếu credential) hoặc trả **0 dòng** thì ghi log WARNING và
> thử nguồn kế tiếp; hết chuỗi mới báo ERROR. Nhờ vậy một vendor lỗi không làm
> universe mất điểm, và cấu hình vẫn là nguồn sự thật duy nhất.

---

# 8. Mục mở / TO VERIFY (§8 bản Anh — chặn việc collector T004)

1. Luồng đăng ký **FiniPro**, cơ chế token và giới hạn tần suất từng call.
   **Đã giải phần thị trường (2026-09-27):** `Market/AccessToken` nhận
   `consumerID`/`consumerSecret` và trả JWT (provider cache theo tiến trình, tự
   xin lại khi gặp 401); `Market/DailyOhlc` + `Market/DailyIndex` đã kiểm chứng
   (68 + 34 dòng, `VERIFIED_2026-09-27`). Còn chờ: hạn mức tần suất chính thức
   theo gói. **Đã đóng câu hỏi endpoint cơ bản/sự kiện (2026-10-03):** danh
   sách hàm FastConnect Data chỉ có 9 endpoint thị trường
   (`AccessToken/Securities/SecuritiesDetails/DailyOhlc/DailyIndex/IndexList/
   IndexComponents/IntradayOhlc/DailyStockPrice`) — **không có** BCTC. BCTC của
   SSI nằm ở sản phẩm **iExcel** (`IE.BalanceSheet/IncomeStatement/CashFlow`)
   không có REST API ⇒ vai trò `fundamental` chuyển sang `vndirect_financials`.
2. URL endpoint & schema response chính xác cho `vndirect`, `tcbs`, `dsc`
   (API không tài liệu — phải snapshot-test). **Đã giải cho `yahoo` ngày
   2026-09-25** (chart v8 đã kiểm chứng + ghi trong
   `tests/fixtures/yahoo_chart_sample.json`): OHLCV đã điều chỉnh tách (provider
   un-adjust qua `events=split`), không có trường turnover
   (`trading_value` = xấp xỉ close × volume), bỏ dòng placeholder volume 0,
   `meta.fullExchangeName` gán sai sàn ngoài HOSE.
   **Mở cho BCTC (GĐ 2):** `vndirect_financials` viết mapping phòng thủ
   (chấp nhận nhiều tên trường, bỏ dòng thiếu giá trị, `published_at` thiếu →
   `NULL`) nhưng `finfo-api.vndirect.com.vn` **timeout từ host dev** nên payload
   thật chưa snapshot được → `MAPPING_TO_VERIFY_2026-10-03`. Khi có mạng, chạy
   `ingest --dataset financials --source vndirect_financials --symbols FPT`
   và ghi fixture vào `tests/fixtures/vndirect_financials_sample.json`.
3. Độ phủ từng mã của **khối ngoại / tự doanh** ở vendor dự phòng.
4. Khả năng diễn đạt **`report_date` (ngày nộp)** và hình thù **diff điều chỉnh** của NCC Việt —
   kiểm chứng thiết kế snapshot-diff ở §4.2.
5. Độ chính xác **gắn mã cho tin** (khớp thực thể tiếng Việt) cho `news_symbols`.
6. Đọc cấp phép feed chính thức HOSE/HNX (hệ số sự kiện doanh nghiệp cho
   `adjusted_prices`) trước khi bật provider `hose`/`hnx`.

> Ghi chú trung thực: provider trả phí/chưa kiểm chứng là dự phòng chất lượng;
> chúng không phải nguồn chân lý.
