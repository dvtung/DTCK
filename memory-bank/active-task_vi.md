# Bộ nhớ dự án — Task đang làm (Bản tiếng Việt)

> Thuật ngữ chuyên môn (tên bảng, biến môi trường, lệnh, đường dẫn) giữ nguyên tiếng Anh.

## Task: T021 — Module "Chấm điểm & Gợi ý cổ phiếu đa chiến lược" (3 hồ sơ: ngắn/trung/dài hạn)

**Trạng thái:** ĐANG TRIỂN KHAI — GĐ 1 HOÀN THÀNH (2026-10-03)
**Nguồn yêu cầu:** `docs/cline_prompt_stock_scoring_module.md` (đã duyệt kế hoạch 6 giai đoạn).
**Quyết định đã chốt (user, 2026-10-03):** financials dùng `ssix_finipro` trước, fail thì sang nguồn khác · adapter mới cho SSI được phép · chỉ email (không Telegram) · **bảng mới** hoàn toàn, không sửa `factor_scores` · tuần tự GĐ 1→6, VN30 + hồ sơ **trung hạn** trước.

### Tiến độ GĐ:
- [x] **GĐ 1 — Cấu hình + schema + khung module (2026-10-03)**
  - `configs/strategy_weights.yaml` (`strategy_v1.0`: 3 profile × 7 nhóm, grade A≥80/B≥65/C≥50, `require_trend_confirmation: [short]`) + `configs/redflag_thresholds.yaml` (`redflag_v1.0`: thanh khoản ≥1 tỷ VND/20 phiên, lỗ ≥2 năm + OCF âm, D/E ≤2.0 override `banking/securities: null`, `realestate: 3.0`).
  - `src/common/models/strategy.py` (mới): `StrategyScore` + `StrategyRecommendation` (PK `(stock_id, trade_date, strategy)`); `financial_statements.published_at TIMESTAMPTZ NULL` (chống look-ahead).
  - Migration `0005_strategy_scoring.py`: create idempotent (pattern 0002, `inspector.has_table`), hypertable `strategy_scores` theo `trade_date` (1 month), `ADD COLUMN IF NOT EXISTS published_at`.
  - Package `src/quant/strategy/`: `groups.py` (7 nhóm + `GROUP_COLUMNS`), `config.py` (nạp/validate YAML, tổng trọng số = 1.0), `scoring.py` (`score_profile`: chuẩn hoá lại, Σ contribution = 1, confidence theo coverage), `recommend.py` (grade A–D, `short` không confirm trend → capped C, disclaimer §3), `redflags.py` (evaluate theo YAML, input None → `unchecked`, không flag).
  - Test `tests/unit/test_strategy_scoring.py` (30 test) + `test_models.py` thêm 2 bảng.
- [x] **GĐ 2 (phần ETL) — Provider + pipeline financials/events (2026-10-03)**
  - **Kết luận SSI (FACT, 2026-10-03):** danh sách hàm FastConnect Data (official docs) chỉ có 9 endpoint thị trường — **không có** báo cáo tài chính; BCTC của SSI nằm ở sản phẩm **iExcel** (`IE.BalanceSheet/IncomeStatement/CashFlow`) không có REST API. → Theo quyết định "SSI không được thì chọn nguồn khác", vai trò `fundamental` chuyển sang **`vndirect_financials`**.
  - `src/data/records.py`: + `FinancialRow`, `EventRow`, `MacroPoint`.
  - `src/data/providers/base.py`: + `fetch_financials` / `fetch_events` / `fetch_macro`.
  - `src/data/providers/vndirect_financials.py` (mới): `VNDirectFinancialProvider` — mapping **phòng thủ** (nhiều tên trường, bỏ dòng thiếu giá trị, `published_at` thiếu → `None`/`NULL`, KHÔNG bịa).
  - `src/data/providers/fixture.py`: + `build_financial_fixture_rows` / `build_event_fixture_rows` (offline; `published_at` = cuối quý + 45 ngày), cờ `include_financials`/`include_events`.
  - ETL đầy đủ: `collect_financials`/`collect_events` → `validate_*` → `normalize_*` → `ingest_financials`/`ingest_events` (chunked, snapshot-diff lưỡng thời: đổi giá trị → đóng `valid_to` + chèn bản mới; chỉ lệch `published_at` → sửa tại chỗ; không đổi → no-op; events dedup app-level `(stock_id, event_type, event_date)`).
  - Registry: `financial_provider_chain()` + `create_provider("vndirect_financials")`; `configs/sources.yaml` thêm provider `vndirect_financials` (`MAPPING_TO_VERIFY_2026-10-03`), `selection.fundamental/corporate_events` trỏ tới nó.
  - CLI: `ingest --dataset {financials,events}` + `--period-types`; fixture provider tự bật financials/events theo dataset.
  - Test mới: `tests/unit/test_vndirect_financials.py` (14) + `tests/integration/test_financial_ingestion.py` (2, ghi trong transaction rollback theo KI-013).
  - Docs: `docs/DATA_SOURCES_vi.md` (bảng provider, miền, mục 8.1/8.2) + `helper/resources_vi.md` (3 lệnh CLI mới).
- [x] **GĐ 2 (phần nguồn) — Tìm nguồn BCTC thật: CafeF `apiweb` VERIFIED + nạp VN30 (2026-10-03)**
  - **`cafef_financials` (chính):** `CafefFinancialProvider` — 3 endpoint `apiweb.cafef.vn` (`GetReportCDKT` CĐKT · `GetReportDetail` KQKD · `GetReportLCTT` LCTT), tham số `symbol/pageIndex/pageSize/reportType/TypeTime=QUY|NAM`. **Kiểm chứng 2026-10-03**: cả 3 trả `200` với dữ liệu FPT thật; snapshot payload ghi vào `tests/fixtures/cafef_financials_sample.json` (162 KB).
  - Payload: response `{isSuccess, value:{templace, data}}`; `data` **gom nhóm** (CĐKT/LCTT) hoặc **phẳng** (KQKD) → parser bóc cả hai; kỳ `"Q2-2026"` / `"2025"`, `quater=0` cho kỳ năm; **không có ngày công bố** ⇒ `published_at = NULL` (trung thực, không bịa).
  - **Phát hiện dữ liệu thật:** một số chỉ tiêu LCTT trả giá trị rác (vd `-1.59e27` cho `HDKD_12`) vượt `Numeric(24,4)` → thêm `MAX_ABS_FINANCIAL_VALUE = 1e20` + `financial_key()` + `corrupt_financial_keys()`: bị **gắn cờ trong issues + bỏ khỏi bản ghi** (không bao giờ scale/round), cùng nhóm với guard OHLC.
  - `configs/sources.yaml`: provider `cafef_financials` (`VERIFIED_2026-10-03`, `priority 90`), `selection.fundamental: cafef_financials`, fallback `vndirect_financials`.
  - **Nạp live VN30 (fact):** `ingest --dataset financials --source cafef_financials --symbols <30 mã VN30> --period-types QUARTER YEAR` → `fetched=204065 written=190125 skipped=13940 issues=2803 quality=99.58`. CSDL: **201.402 dòng `financial_statements`, đủ 30 mã**, 113.157 quý + 88.245 năm, BALANCE 120.988 / CASHFLOW 50.894 / INCOME 29.520, khoảng `2005-12-31 → 2026-06-30`. Kiểm chứng: FPT doanh thu Q2-2026 = `13.788.503.461.199` VND (đúng số liệu thật). Chạy lại → `written=0` (idempotent).
  - Test mới: `tests/unit/test_cafef_financials.py` (11).
- [x] **GĐ 2 (phần còn lại) — Sự kiện doanh nghiệp + Vĩ mô thật (2026-10-03)**
  - **Sự kiện doanh nghiệp ← Yahoo `events=div,split`** (cùng endpoint chart đã VERIFIED): thêm `YahooChartProvider.fetch_events` (`SUPPORTED_DATASETS = {prices, events}`), `EventRow` cho DIVIDEND (`cash_amount`) và SPLIT (`numerator/denominator/ratio`); `announced_date = NULL` (Yahoo không công bố). **Sửa lỗi tiềm ẩn:** `HttpJsonProvider.__init__` ghi instance `SUPPORTED_DATASETS` đè class attr của subclass → chuyển lên class-level. **Fix JSONB:** `normalize_events` chuyển `Decimal` trong `details` → `float` (JSONB không serialize Decimal).
    - Nạp live VN30 `since 2020-01-01` → **fetched=238 written=238**; CSDL: 238 dòng (154 DIVIDEND + 84 SPLIT), 29 mã, 2020-02-04 → 2026-10-02.
  - **Vĩ mô ← IMF datamapper** (`ImfMacroProvider`, id `imf_worldbank`): `GDP_GROWTH_PCT` (NGDP_RPCH) + `CPI_INFLATION_PCT` (PCPIPCH) cho VNM; **chỉ lưu năm đã kết thúc** (`max_year_offset=1`) — dự báo WEO không bao giờ được ghi.
    - Nạp live `2010→2026` → **fetched=32 written=32 quality=100.00**; CSDL: 32 dòng, 2010-12-31 → 2025-12-31 (unit percent).
  - ETL: `collect_macro`/`validate_macro`/`normalize_macro`/`ingest_macro` (upsert PK `(indicator_code, period_date)`); CLI `--dataset {events,macro}` + `--indicators`.
  - `configs/sources.yaml`: `yahoo` thêm role `corporate_events`; `imf_worldbank` thêm `endpoints.macro` (`VERIFIED_2026-10-03`) + priority 80; `selection.corporate_events: yahoo`, `selection.macro: imf_worldbank`.
  - Test mới: `tests/unit/test_events_macro.py` (9) + integration `test_macro_ingestion_roundtrip_and_upsert`.
- [~] **`published_at` — QUYẾT ĐỊNH (giữ nguyên NULL):** cả CafeF (BCTC) và Yahoo (sự kiện) **không trả ngày công bố**, nên cột giữ `NULL` — không bịa. Chống look-ahead ở GĐ 3 sẽ dùng `COALESCE(published_at, report_date + lag)` với `lag` từ cấu hình (mốc pháp lý VN: 45 ngày quý / 90 ngày năm) — chọn mốc **muộn nhất** là hướng an toàn (không bao giờ thấy dữ liệu sớm hơn thực tế).
- [x] **GĐ 3 — Feature Engine + chuẩn hoá ngành (2026-10-03)**
  - `configs/strategy_features.yaml` (`features_v1.0`): `publication_lag_days {QUARTER: 45, YEAR: 90}` (mốc pháp lý VN), `price_lookback_days`, `history`.
  - `src/quant/strategy/features.py`: `FeatureSnapshot`/`PeriodValues` + **24 feature thuần** có registry (`FEATURES`) với `group`, `direction` (±1), `exclude_industries`.
    - technical: `price_vs_sma20/50/200`, `return_20d`, `return_63d`, `rs_vs_index_63d`, `macd_hist_pct`, `atr20_pct` (−1)
    - moneyflow: `avg_value_20d`, `volume_ratio_20d`
    - growth: `revenue_yoy`, `net_profit_yoy`, `revenue_cagr_3y`
    - quality: `roe_ttm`, `roa_ttm`, `net_margin`, `cfo_to_net_profit_ttm`
    - valuation: `pe_ttm` (−1), `pb` (−1), `dividend_yield_ttm`
    - macro: `catalyst_event_ttm`
    - governance: `debt_to_equity` (−1), `current_ratio`, `redflag_free` — **loại trừ ngân hàng/chứng khoán/bảo hiểm** cho bộ đòn bẩy/định giá chung.
  - Mã VAS dùng (đã kiểm chứng từ payload thật): `10` doanh thu, `20` lãi gộp, `60` LNST, `70` EPS, `100/110/270/300/310/400` CĐKT, `HDKD_20` LCTT. `pb` suy ra số cổ phiếu = LNST TTM ÷ EPS TTM (diễn giải có ghi chú, không bịa).
  - `src/quant/strategy/feature_engine.py`: `compute_snapshots` (đọc prices/index_prices/financial_statements/corporate_events + industry), **luật chống look-ahead** `_usable_from = published_at hoặc report_date + lag`, `compute_group_scores` (percentile theo vũ trụ, áp `direction`, thiếu dữ liệu → loại khỏi mẫu số + báo `missing`), `compute_and_store_features` (upsert bảng `features`, tên `grp:<nhóm>` cho điểm nhóm).
  - CLI `compute-features --as-of --symbols`.
  - **Kiểm chứng live (fact):** `compute-features` cho 30 mã VN30 → **written=761**; CSDL `features` 761 dòng/30 mã, đủ 7 nhóm; FPT: P/E 12.01, P/B 3.20, ROE 26.7%, doanh thu YoY −17.1%, price/SMA200 −20.7%; top growth VIC 90.6 / VHM 85.7 / VCB 82.6.
  - Test mới: `tests/unit/test_strategy_features.py` (13) + integration `test_feature_engine_persists_and_is_idempotent`.
  - **Hạn chế đã biết (ghi nhận cho GĐ 4):** `percentile_rank` (strictly-less-than) làm feature nhị phân/bằng điểm thoái hoá — `catalyst_event_ttm` bằng nhau ở mọi mã ⇒ `grp:macro` = 0 cho tất cả. Cần dùng mid-rank cho ties, hoặc thay catalyst bằng feature liên tục.
- [x] **GĐ 4 — Red flag + chấm điểm 3 chiến lược + gợi ý + job scheduler (2026-10-03)**
  - **Sửa lỗi GĐ 3 (mid-rank):** thay `percentile_rank` (strictly-less-than) bằng `_rank_percentile` mid-rank `(less + 0.5×equal)/n×100` → feature nhị phân/bằng điểm không còn thoái hoá về 0 (live: `grp:macro` từng = 0 mọi mã; nay 66.67/16.67 đúng thứ tự).
  - `src/quant/strategy/recommend.py`: thêm `atr()` (close-to-close, ghi chú rõ là xấp xỉ), `price_levels()` (vùng mua = `[close−ATR, close+0.25·ATR]`, stop = `close−2·ATR`, target = `close+3·ATR`, R/R = 1.50), `trend_confirmed()` (`close > SMA20 > SMA50` — cổng cho grade A/B của `short`).
  - `src/quant/strategy/job.py`: `compute_and_store_strategy_scores(engine, as_of, symbols)` — chụp dữ liệu as-of → tính features + 7 nhóm → `score_profile` × 3 hồ sơ → `build_recommendation` (gắn trend gate cho `short`) → upsert `strategy_scores` + `strategy_recommendations` (JSONB cast qua `cast(:x as jsonb)` + `json.dumps` — psycopg không adapt dict/list).
  - **Scheduler:** job `daily_strategy_scoring` Mon–Fri **16:15 ICT** (sau scoring 16:00, cùng phiên đóng) — biến `scheduler_strategy_hour/minute` trong `apps/api/config.py`.
  - CLI `strategy-scores`.
  - **Kiểm chứng live (fact):** `strategy-scores` 30 mã VN30 as_of 2026-10-03 → **scored=90 skipped=0 written=90**; CSDL: `strategy_scores`=90, `strategy_recommendations`=90. Phân bố grade: mid A=1 B=2 C=9 D=18 · short A=1 B=1 C=11 D=17 · long B=2 C=13 D=15. FPT mid: score 47.2 → D, vùng mua 61.125–62.344, stop 60.150, target 65.025, R/R 1.50, confidence 0.6863. HDB đạt **A** (mid 81.2 / short 80.1). Lý do tiếng Việt có % đóng góp (vd "Nhóm 'technical' đóng góp 62% điểm (giá trị 92/100)").
  - Test: `tests/unit/test_strategy_job.py` (13) + `test_worker_scheduler.py` (+1 job đăng ký + thứ tự sau 16:00) + integration `test_strategy_scoring_persists_and_is_idempotent`.
- [x] **GĐ 5 — Backtest module điểm + báo cáo (2026-10-03)**
  - `src/quant/strategy/backtest.py`: `load_backtest_data` (OHLCV thật từ `prices`/`index_prices`, lịch nến theo benchmark, **carry-forward ngày ngưng GD** với `volume=0` — quy ước, không ghi ngược vào DB; mã chưa có giá trước ngày đầu → **loại** thay vì bịa), `rebalance_dates`, `score_schedule` (mỗi ngày rebalance chấm điểm **as-of** — dùng đúng luật chống look-ahead của GĐ 3), `top_weights` (top-N trọng số đều, tie-break theo mã), `build_strategy` (trả weights đúng ngày rebalance, `{}` ngày khác → engine giữ vị thế), `_benchmark_metrics` (VNINDEX mua & giữ cùng cửa sổ), `run_strategy_backtest` → `BacktestReport` (metrics + benchmark).
  - CLI `backtest-strategy --profile --top-n --rebalance-days --start --end` (in bảng strategy vs benchmark).
  - **Kiểm chứng live (FACT, 2025-10-01→2026-09-30, VN30, top-5, 21 phiên):**
    | Hồ sơ | Tổng LN | Sharpe | MaxDD | Thắng | PF | Vòng quay |
    |---|---|---|---|---|---|---|
    | short | −15.22% | −0.43 | −35.97% | 50.9% | 0.75 | 17.5× |
    | mid | −17.09% | −0.66 | −24.48% | 43.5% | 0.64 | 13.5× |
    | long | −14.44% | −0.56 | −32.73% | 42.5% | 0.63 | 9.8× |
    | **VNINDEX** | **+6.22%** | **+0.40** | **−16.38%** | — | — | 0 |
    → **cả 3 hồ sơ thua chỉ số** trong cửa sổ này.
  - Báo cáo + đề xuất tinh chỉnh: **`docs/strategy_backtest_report_vi.md`** (6 đề xuất ưu tiên: cổng chế độ thị trường `VNINDEX > SMA50`, giảm vòng quay (rebalance 63 phiên + vùng đệm top-10), walk-forward tinh chỉnh trọng số, bổ sung dữ liệu governance/khối ngoại, mở rộng VN100, kiểm chứng đa cửa sổ). **Khuyến nghị KHÔNG bật tín hiệu thật ở trạng thái hiện tại** (§3 + ADR-007).
  - Test: `tests/unit/test_strategy_backtest.py` (11) + integration `test_strategy_backtest_runs_and_reports_benchmark`.
- [x] **GĐ 6 — API + dashboard + cảnh báo email + mở rộng VN100 (2026-10-04)**
  - **API** — router mới `apps/api/routers/strategy.py` + `apps/api/services/strategy_service.py` (`DbStrategyService` đọc CSDL / `NullStrategyService` trả rỗng trung thực khi không có DB; dependency `StrategyDep` trong `dependencies.py`):
    - `GET /api/v1/strategy/rankings?strategy=&universe=vn30|vn100&limit=&offset=` → envelope `{items,total,limit,offset}` — mỗi dòng có điểm 7 nhóm, grade, vùng mua/cắt lỗ/mục tiêu, R/R, confidence, lý do/rủi ro tiếng Việt, `data_flags`, `disclaimer` §3
    - `GET /api/v1/strategy/{symbol}` → 3 hồ sơ của 1 mã
    - `GET /api/v1/strategy/{symbol}/history?strategy=&limit=`
    - unknown profile → **422**, unknown symbol → **404**
  - **Dashboard** — trang thứ 10 **"Chấm điểm chiến lược"** (icon `bars`): chọn hồ sơ + vũ trụ, bảng xếp hạng, biểu đồ 30 mã tô màu theo grade, expander giải thích nhóm chỉ số/lý do/rủi ro + disclaimer. AppTest 10/10 trang; **kiểm chứng render với dữ liệu thật** (AppTest + API thật): không exception, 1 dataframe 30 dòng, cột đủ.
  - **Cảnh báo đổi grade** — `src/quant/strategy/alerts.py`: `detect_grade_changes` (so 2 phiên chấm điểm gần nhất, im lặng khi <2 phiên), `build_change_email` (HTML thuần, escape ký tự, luôn kèm §3), `send_grade_change_alert` (dùng lại SMTP stack T018 — `NotificationService.get_mailer()` + `get_recipients()`, báo lỗi rõ nếu chưa cấu hình/空 danh sách). Hook vào `scheduled_strategy_scoring_job` (chỉ gửi khi **có thay đổi**) + CLI `notify-strategy-changes [--dry-run]`.
  - **VN100** — `compute-features` + `strategy-scores` trên 100 mã: **features written=1599**, **strategy scores written=300** (100×3). Lọc `universe=vn100` trên API → total=100; `vn30` → 30; không lọc → 100.
  - **Test**: `tests/unit/test_strategy_api.py` (9) + `test_strategy_alerts.py` (9) + `test_dashboard_app.py` (10 trang) + integration (2: detect delta + không cảnh báo giả).
  - **Sửa lỗi trong lúc làm:** test detect dùng ngày `strategy_scores` chứ không phải ngày `prices` (chúng khác nhau: prices max 2026-10-02 vs scores 2026-10-03) → thêm helper `_latest_scored_date`.
- [x] **Toàn bộ GĐ 1–6 của module "Chấm điểm & Gợi ý cổ phiếu đa chiến lược" hoàn tất (2026-10-04).** Xem `docs/strategy_backtest_report_vi.md` trước khi cân nhắc bật tín hiệu thật.
- [x] **Bổ sung chọn khung thời gian VNINDEX & tích hợp Chấm điểm chiến lược vào Email (2026-10-04)**:
  - Dashboard: Bộ chọn 9 khung thời gian cho biểu đồ nến ngày VNINDEX (`Tất cả`, `3 năm`, `2 năm`, `1 năm`, `6 tháng`, `3 tháng`, `1 tháng`, `2 tuần`, `1 tuần`) với `rangebreaks` cuối tuần.
  - Sửa lỗi `AttributeError: get_strategy_rankings`: Thêm mount `./src:/app/src` và `./configs:/app/configs` vào `dashboard` trong `docker-compose.yml`, fallback `STRATEGY_DISCLAIMER`.
  - Email báo cáo thị trường (`src/notifications/`): Tích hợp bảng Top 10 mã VN30 cho cả 3 hồ sơ (Ngắn hạn, Trung hạn, Dài hạn) với 8 cột (Hạng, Mã, Điểm, Xếp hạng A–D, Vùng mua thấp–cao, Cắt lỗ, Mục tiêu, Độ tin cậy) kèm hộp giải thích chi tiết 6 thông tin cơ bản. Nối tự động qua `NotificationService`, router API và scheduler worker. Unit test `test_renders_strategy_rankings_and_explanations` pass 100%.
- [x] **Đổi Delta Chỉ số VN30/VNINDEX từ % sang Số điểm Tăng/Giảm (2026-10-04)**:
  - Khắc phục lỗi hiển thị luôn là `0.0%` do nguồn SSI lưu `open = close`.
  - `apps/api/schemas.py`: Bổ sung `change` và `change_pct` vào `IndexPriceOut`.
  - `apps/api/services/db_market.py` & `market_data.py`: Dùng `lag(close)` tính mức tăng giảm điểm số so với phiên trước.
  - `apps/dashboard/app.py`: Đổi metric delta VN30 sang số điểm tăng/giảm (`-14.58 điểm`), bổ sung cột `"+/- điểm"` trong bảng Chỉ số và delta VNINDEX dưới biểu đồ nến.

### Kiểm chứng GĐ 1 (fact, 2026-10-03):
- `ruff check .` → All checks passed (kèm sửa lỗi lint có sẵn của T020 trong `apps/dashboard/app.py` + `scripts/backfill_history.py`).
- `mypy src apps` → **147 tệp** sạch.
- `pytest tests/unit` → **616 passed, 3 skipped** (586 cũ + 30 mới).
- `pytest tests/integration` → **30 passed, 1 failed pre-existing**: `test_news_reader_exposes_linked_symbols` — `news` đã 210 dòng > `DEFAULT_LIMIT=200`, fixture 2026-08-05 bị sort DESC loại khỏi top 200 (xác minh fail cả khi gỡ hết thay đổi GĐ 1; cần sửa ở task riêng).
- Migration: `alembic upgrade head` → `0005_strategy_scoring (head)`; downgrade `0004` → upgrade lại OK.

---

## Task: T020 — Backfill Dữ liệu Lịch sử (2020–2026) + Huấn luyện lại ML + Trang Lịch sử Worker cho Dashboard
## Task: T020 — Backfill Dữ liệu Lịch sử (2020–2026) + Huấn luyện lại ML + Trang Lịch sử Worker cho Dashboard

**Trạng thái:** HOÀN THÀNH (2026-09-30)
**Mục tiêu:** (1) Nạp dữ liệu lịch sử từ 2020-01-01 tới nay cho toàn bộ 138 mã cổ phiếu và chỉ số (VNINDEX, VN30); (2) Chạy lại tính điểm nhân tố quant; (3) Huấn luyện lại mô hình ML dự đoán xu hướng giá từ CSDL và lưu vào Model Registry; (4) Thêm trang "Lịch sử Worker" trên Dashboard Streamlit.

### Sản phẩm:
- [x] `scripts/backfill_history.py` — nạp EOD giá 138 mã qua chuỗi `ssix_finipro → yahoo`, nạp `index_prices`, tính toán lại điểm số quant `compute_and_store_scores`, và gọi pipeline huấn luyện lại mô hình `ModelTrainer(algorithm="xgboost")` kết nối CSDL TimescaleDB.
- [x] CSDL: Tổng số bản ghi `prices` tăng vọt từ ~67.000 lên **218.736 bản ghi** (từ 02/01/2020 đến 30/09/2026).
- [x] ML: Mô hình `price_direction_xgb@1.0.0` được fit trên tập dữ liệu lịch sử mở rộng từ CSDL thật, lưu artifact vào CSDL `model_registry`.
- [x] `apps/dashboard/app.py`: Bổ sung trang thứ 9 **"Lịch sử Worker"** (3 tab: Lịch trình APScheduler 8 job, Nhật ký gửi email tự động, Lệnh vận hành CLI).
- [x] `tests/unit/test_dashboard_app.py`: Cập nhật fixture danh sách trang (9 trang), chạy 10/10 test AppTest pass.

### Kiểm chứng (fact, 2026-09-30):
- `MARKET_DATA_SOURCE=memory pytest tests/unit` → **586 passed, 3 skipped**.
- `pytest tests/integration` → **31 passed**.
- Headless AppTest dashboard → **9/9 trang render hoàn hảo không exception**.

---

## Task: MAINT-2026-09-29 — Sửa test xoá dữ liệu thật (KI-013) + Worker mất giá đóng cửa (KI-014)

**Trạng thái:** HOÀN THÀNH (2026-09-29)
**Mục tiêu:** (1) `pytest` không bao giờ được sửa/xoá dữ liệu CSDL phát triển; (2) `daily_eod_ingestion` phải nạp đủ **cổ phiếu + chỉ số** cho phiên hôm nay và tự vá khi nhà cung cấp lỗi lúc 15:30.

### Sản phẩm:
- [x] `tests/integration/conftest.py` — fixture `isolated_session_factory` (service ghi trong transaction luôn rollback); `tests/integration/test_email_notifications.py` bỏ `_clear_smtp_configs()` + thêm bài regression `test_isolated_writes_never_reach_the_shared_database` (KI-013).
- [x] `src/data/freshness.py` (mới) — `expected_session_date`, `stale_datasets`, `is_intraday_snapshot`, `latest_trade_dates`, `latest_ingested_at` (hàm thuần thuần để test được, SQL mỏng).
- [x] `apps/worker/main.py` — `scheduled_eod_ingestion` nạp kèm `index_prices` (qua `SCHEDULER_EOD_INDICES` + `provider.supports`), job **`daily_eod_catchup` 15:50** (chỉ nạp khi `prices`/`index_prices` cũ hơn phiên đã đóng), cảnh báo `intraday snapshot` trong `scheduled_scoring_job`, log freshness sau mỗi lượt nạp (KI-014).
- [x] `apps/api/config.py` — `scheduler_eod_indices`, `scheduler_eod_include_intraday_session`, `scheduler_eod_catchup_hour/minute`, `scheduler_session_close_hour/minute` + helper `parse_codes`.
- [x] `.env.example`, `helper/deployment_vi.md`, `helper/resources_vi.md`, `docs/DEPLOYMENT_vi.md`, `memory-bank/known-issues_vi.md` (KI-013/KI-014), `docs/index.html`, `docs/structure.html`.

### Kiểm chứng (fact, 2026-09-29):
- `ruff check .` + `mypy apps src` (**140 tệp**) sạch; `pytest -q` → **617 passed, 3 skipped** (620 thu thập: unit 589 + integration 31), exit 0.
- Live: `daily_eod_catchup` đăng ký trong worker; catch-up khi dữ liệu mới → bỏ qua không gọi vendor; lượt EOD đầy đủ → `prices fetched=820` + `index_prices fetched=12` + `all scheduled datasets current for 2026-09-29`; khi mô phỏng phiên chưa đóng → cảnh báo `prices, index_prices behind the last closed session …`.
- Backfill trong lúc điều tra: `prices` 2026-09-29 (136 dòng, giá đóng cửa thật), `index_prices` VNINDEX/VN30 2026-09-29, `factor_scores` 136 dòng — trước đó chỉ có ảnh chụp 11:30 và chỉ số đóng băng từ 2026-09-25.
- **Còn mở:** `market_regimes` vẫn 0 dòng → `/api/v1/market/regime` trả `UNKNOWN` (không có job nào viết bảng này — cần quyết định thiết kế riêng); chỉ số SSI lưu OHLC phẳng vì `Market/DailyIndex` không trả về OHLC.

---

## Task: T019 — Thiết kế lại giao diện Dashboard chuẩn BI tài chính chuyên nghiệp

**Trạng thái:** HOÀN THÀNH (2026-09-28)
**Mục tiêu:** Nâng cấp toàn diện thẩm mỹ Streamlit dashboard DTCK sang phong cách tài chính BI chuẩn mực (Bloomberg / Refinitiv inspired, palette chuyên nghiệp, typography phân cấp rõ ràng, loại bỏ emoji chrome, SVG icons, thống nhất layout biểu đồ Plotly).

### Sản phẩm:
- [x] `apps/dashboard/theme.py`: Design tokens, dark sidebar / light surface CSS sheet, builder hàm HTML an toàn (`app_bar`, `page_header`, `section_label`, `side_card`, `brand_html`, `footer`), inline SVG icon path registry.
- [x] `apps/dashboard/app.py`: Gỡ bỏ emoji trong danh mục trang điều hướng; tích hợp `theme.page_header` trên toàn bộ 8 trang; áp dụng `theme.chart_layout` và cấu hình token cho toàn bộ các biểu đồ Plotly (candlestick, MA lines, volume, bar chart, score breakdown); thêm `theme.footer` với disclaimer §3 và dependency chips.
- [x] `tests/unit/test_dashboard_theme.py`: 17 unit test kiểm chứng tokens, SVG generator, HTML builders, CSS injection, Plotly config.
- [x] `tests/unit/test_dashboard_app.py`: Cập nhật và bổ sung 9 test headless AppTest kiểm tra render 8/8 trang không lỗi và hoàn toàn sạch bóng emoji chrome.

### Kiểm chứng:
- Chạy toàn bộ test dashboard: **69/69 passed** (`test_dashboard_app.py`, `test_dashboard_theme.py`, `test_dashboard.py`).
- Cú pháp và kiểu dữ liệu: `ruff check`, `ruff format --check`, `mypy` đạt 100% không phát sinh cảnh báo hay lỗi.

---


## Task: T018 — Module gửi email tự động (Gmail SMTP) + Trang quản trị dashboard

**Trạng thái:** HOÀN THÀNH (2026-09-28)
**Mục tiêu:** (1) gửi email báo cáo Tổng quan tự động Thứ 2–6 lúc 08:00 và 15:30 qua Gmail SMTP; (2) trang **📧 Quản lý Email** trên dashboard quản lý người nhận, tài khoản SMTP, lịch gửi, gửi thử + preview.

### Sản phẩm:
- [x] `src/notifications/` — `report_generator.py` (HTML Tổng quan: KPI, Top 10 tăng/giảm vs MA20, VN30 + P(tăng 5D), disclaimer §3), `smtp_mailer.py` (stdlib: STARTTLS 587/SSL 465, map lỗi AUTH/disconnect/recipient sang tiếng Việt), `service.py` (`NotificationService`: recipients/SMTP/schedule/logs/dispatch).
- [x] `src/common/models/notifications.py` + migration `0003_email_notifications` (4 bảng; 42 bảng tổng).
- [x] Router `notifications` — 11 thao tác `/api/v1/notifications/*` (CRUD recipients, smtp, schedule, send-test, preview-html, logs).
- [x] Worker: 2 cron Mon–Fri **08:00** + **15:30** (`Asia/Ho_Chi_Minh`) → scheduler **5 job**.
- [x] Dashboard **📧 Quản lý Email** (5 tab: gửi thử/preview HTML, người nhận, SMTP Gmail, lịch gửi, logs); validation regex stdlib (không `email-validator`); cảnh báo password ≠ 16 ký tự (không phải App Password).

### Kiểm chứng (fact, 2026-09-28):
- **566 unit passed + 3 skipped** (569 thu thập) và **29 integration passed**; `ruff check` + `mypy` (**139 tệp**) sạch.
- Test integration ghi trong transaction rollback (`isolated_session_factory`) ⇒ **không** sửa/xoá dữ liệu thật; regression `test_isolated_writes_never_reach_the_shared_database` bảo vệ (KI-013).
- Live trong container: build HTML 16 KB từ service thật, worker đăng ký đủ 5 job (`daily_morning_email_report`, `daily_afternoon_email_report`), trace SMTP đến AUTH rồi 535 → map sang hướng dẫn App Password.
- **Còn chặn vận hành (phía người dùng, không phải bug repo):** Gmail yêu cầu App Password 16 ký tự cho SMTP (mật khẩu thường → 535; thử lại nhiều lần → Gmail đóng kết nối `SMTPServerDisconnected`). Người dùng tự tạo tại `myaccount.google.com/apppasswords` rồi lưu trên dashboard.

### Bối cảnh đã đóng góp (giữ nguyên cho truy vết):
- T016 (Universe VN100/đa sàn + nến VNINDEX + Top 10 + login JWT, 2026-09-27): +11 bài ⇒ **510 unit, 20 integration**, ruff+mypy 133 tệp.
- T018 (2026-09-27): +11 bài ⇒ **521 unit, 28 integration**, ruff+mypy 138 tệp.
- `a39e130` (2026-09-28): map lỗi SMTP sang hướng dẫn App Password + cảnh báo password; +2 bài ⇒ **523 unit, 28 integration**.

---

## Task: T015c — Dashboard dùng dữ liệu thật + Bảng Đánh giá & Dự đoán VN30 + Form Backtest

**Trạng thái:** HOÀN THÀNH (2026-09-27)
**Mục tiêu:** (1) dashboard phải đọc dữ liệu **thật** từ API/CSDL thay vì fixture giả; (2) trình bày đánh giá + dự đoán xu hướng VN30 kèm bằng chứng đáng tin cậy để hỗ trợ quyết định đầu tư; (3) form nhập thông tin backtest; (4) giao diện chuyên nghiệp hơn.

### Nguyên nhân "dữ liệu giả" (đã sửa cả 4):
- [x] `client.py` gọi URL **literal** `{symbol}` → 404 → fallback fixture. Sửa: f-string URL thật + `_fallback` chuẩn hoá mã về template.
- [x] `list_stocks` thiếu `limit` (API mặc định 20/30 mã) → `limit=200`.
- [x] Sidebar hardcode `http://localhost:8000` (container tự gọi chính nó) → đọc `API_HOST` (`DEFAULT_BASE`).
- [x] `./apps/dashboard` chưa bind-mount → thêm vào `docker-compose.yml`.

### Trình bày mục tiêu hệ thống:
- [x] **Tổng quan:** bảng Đánh giá & Dự đoán VN30 (điểm §12 + tín hiệu + **P(tăng 5D) từ model thật** + Gợi ý 🟢/🟡/🔴 tất định + chú giải + footer disclaimer §3), KPI 5 thẻ, Top-10 biểu đồ màu theo tín hiệu.
- [x] **Chi tiết mã:** nến + MA20/MA50 + volume (6 tháng/1 năm/2 năm), chỉ báo §2.4 đủ 15 chỉ báo, khối Dự đoán ML, nút Phân tích AI (thesis + catalysts + risks từ Ollama), Bằng chứng RAG §19.
- [x] **Backtest:** form tạo lượt chạy (chiến lược/vũ trụ/loại/khoảng ngày → `POST /api/v1/backtests`), danh sách nhãn dễ đọc, chỉ số §16 đúng đơn vị.
- [x] **Bộ lọc:** đủ 30 mã VN30 + tìm kiếm theo mã/tên + lọc sàn.
- [x] **Giao diện:** banner gradient, sidebar tối, thẻ KPI viền xanh, bảng bo góc, nav 7 trang unified, footer trạng thái.

### Kiểm chứng trực tiếp (fact, 2026-09-27):
- Container dashboard → API thật: `stocks=30 transport=api`, `FPT prices=496 bars` (đến 2026-09-25), `inds=15 chỉ báo`, `prediction FPT P=0.5058 model v1.0.0`, `ranked=30`.
- AppTest headless trong container với API thật: **7/7 trang render không exception**.
- Bộ test: **499 unit + 20 integration passed**; ruff + mypy (133 tệp) sạch.

---

## Task: T015b — Bền vững hoá ML registry, backfill dữ liệu 2 năm, vận hành tự động & hoàn thiện API

**Trạng thái:** HOÀN THÀNH (2026-09-27)
**Mục tiêu:** (2) model đã huấn luyện phải sống sót qua tiến trình và được API phục vụ thật; (3) nạp lịch sử đủ dài để backtest/ML có ý nghĩa; (4) sao lưu + CI + cảnh báo; (5) sửa lỗi làm tròn payload điểm và nối chiều ghi `POST /backtests` vào CSDL.

### Các công việc đã thực hiện:
- [x] **#2 Registry bền vững** — migration `0002_model_registry_artifact` (`artifact BYTEA`, `target`, `horizon_days`; chu kỳ huấn luyện nullable), `src/ml/registry_store.py` (`save_entry`/`load_entries`/`hydrate_default_registry`), CLI lưu sau khi fit, API `lifespan` nạp lúc khởi động, `/readyz.models`.
- [x] **#3 Backfill + sửa lỗi upsert** — `_UPSERT_CHUNK=1000` trong `src/data/pipelines.py` (lỗi 65.535 tham số truy vấn), nạp 14.810 dòng VN30 2 năm, huấn luyện lại trên 14.066 mẫu.
- [x] **#4 Vận hành** — `scripts/backup_db.sh`, `scripts/health_alert.sh`, `.github/workflows/ci.yml`, `backups/` trong `.gitignore`, mount `./apps` cho container.
- [x] **#5a Làm tròn** — dồn phần dư vào thành phần lớn nhất (`apps/api/services/ranking_payload.py`).
- [x] **#5b JWT/RBAC** — `apps/api/security.py` (HS256 stdlib), login cấp JWT thật với `AUTH_JWT_SECRET`, middleware nhận cả API key cả JWT hợp lệ, `POST /backtests` ép ANALYST/ADMIN.
- [x] **#5c Ghi backtest** — `POST /api/v1/backtests` chèn hàng thật khi DB mode.
- [x] **Kiểm thử** — 491 unit + 20 integration pass; ruff + mypy (133 tệp) sạch.
- [x] **Tài liệu** — `memory-bank/{tasks,known-issues,changelog,current-state,active-task}_vi.md`, `helper/{resources,deployment}_vi.md`, `docs/{DEPLOYMENT,SECURITY}_vi.md`.

### Kiểm chứng trực tiếp (fact đã đo, 2026-09-27):
- `train-model --source db` → `persisted: true`, `roc_auc=0.583` (14.066 hàng); `psql`: `artifact_bytes=64200`, `status=APPROVED`.
- `curl /readyz` → `{"market_source":"auto->db","dependencies":{"database":"connected","qdrant":"up","agents":"llm:qwen3.5","models":"price_direction_xgb@1.0.0"}}`.
- `GET /api/v1/predictions/VCB` → 200 với model đã huấn luyện (`probability_positive=0.5025`) thay vì stub.
- Backfill: `prices` = 14.816 dòng, 30 mã, 2024-09-27 → 2026-09-25; 8 cảnh báo OHLC trên TPB.
- `scripts/backup_db.sh` → `backups/dtck_20260927_110245.sql.gz` (345 KB); `scripts/health_alert.sh` → OK (DB=connected).
- Làm tròn đóng góp: sai lệch tối đa **1e-4 → 0.0**.
- `POST /api/v1/backtests` (DB mode) → 201 + hàng trong `backtests`.

---

## Task: T015a — Production hardening: API-key auth + `/metrics` + `train-model --source db`

**Trạng thái:** HOÀN THÀNH (2026-09-27)
**Mục tiêu:** (a) cổng API-key cho endpoint thay đổi trạng thái & `/metrics` (§32); (b) endpoint Prometheus `/metrics` cho độ trễ request + thời gian chạy agent (§46); (c) mở khóa huấn luyện ML thật (`train-model --source db`, đóng KI-012).

### Các công việc đã thực hiện:
- [x] **API-key auth** — `apps/api/middleware.py::ApiKeyAuthMiddleware` (ASGI): khi `API_AUTH_KEY` đặt, mọi POST/PUT/PATCH/DELETE dưới `/api/v1/` (trừ `/auth/login`) + `GET /metrics` cần `Authorization: Bearer <key>` (`secrets.compare_digest`); sai → 401 phong bì §2.1 + `WWW-Authenticate`. Key rỗng = tắt (mặc định — demo/test không đổi). Nối: `api_auth_key` (`apps/api/config.py`), `docker-compose.yml`, `.env`, `.env.example`.
- [x] **`/metrics` thuần stdlib** — `apps/api/metrics.py` (Prometheus text 0.04, thread-safe, histogram 11 bucket): `dtck_http_requests_total`, `dtck_http_request_duration_seconds`, `dtck_agent_runs_total`, `dtck_agent_duration_seconds`. `MetricsMiddleware` gắn nhãn **route template** (không lộ path thô); agent sync + async ghi qua `_observe_run`/`_execute_observed` (`apps/api/routers/agents.py`); endpoint `GET /metrics` (`apps/api/main.py`). Không thêm dependency `prometheus_client`.
- [x] **`train-model --source {memory,db}`** — `apps/worker/cli.py::_train_market_service` + cờ `--source` (mặc định `memory`); `db` → `DbMarketService`. **Đóng KI-012.**
- [x] **Sửa fallback EOD (bug live tìm thấy)** — SSI kiểm tra credential trễ lúc lấy token → `ingest_eod` ném ngoài `try` hủy cả chuỗi dự phòng; nay toàn bộ gọi nằm trong `try` của vòng lặp nguồn (`apps/worker/main.py`).
- [x] **Kiểm thử (+17)** — `tests/unit/test_t015_hardening.py` (16) + `test_worker_scheduler.py` (1: fallback khi fetch ném lỗi). ⇒ **459 passed, 3 skipped**; ruff sạch; mypy 131 tệp sạch.
- [x] **Tài liệu** — `docs/DEPLOYMENT_vi.md`, `helper/resources_vi.md`, `memory-bank/{changelog,tasks,known-issues,current-state}_vi.md`.

### Kiểm chứng trực tiếp (fact đã đo, 2026-09-27):
- Auth (với `API_AUTH_KEY=live-test-key`): POST không key **401** · key sai **401** · key đúng **200** · GET `/api/v1/stocks/ranked` **200** · `/auth/login` **200** · `/metrics` không key **401** / có key **200** · `/healthz` **200**.
- `POST /api/v1/agents/analyze VCB` (Ollama `qwen3.5` thật) → `succeeded`, `latency_ms=14186`; `/metrics` ghi `dtck_agent_runs_total{status="succeeded",task="analyze"} 1`.
- `train-model --source db` → 616 hàng, `roc_auc=0.702256`, `brier=0.225`, `price_direction_xgb v1.0.0 APPROVED`.
- Job EOD (sau sửa): `ssix_finipro failed: missing SSI_CONSUMER_ID…` → **yahoo `fetched=147 written=147 quality=92.78`**.
- Job scoring: `factor_scores` = 4 dòng `baseline_1.0`, as-of 2026-09-25. Job news: `fetched=1 skipped=1 quality=95.38`.
- `curl /readyz` → `{"market_source":"auto->db", "database":"connected","qdrant":"up","agents":"llm:qwen3.5"}`.

### Ghi chú vận hành:
- **`.env` từng bị reset về bản sao `.env.example` (00:44)** — đã khôi phục cấu hình không secret (`MARKET_DATA_SOURCE=auto`, Ollama `local`/`qwen3.5`/`host.docker.internal:11434`); **`SSI_CONSUMER_ID`/`SSI_CONSUMER_SECRET` phải được nhập lại** — EOD đang tự dự phòng Yahoo nên hệ thống vẫn chạy.
- Shell máy chủ export `MARKET_DATA_SOURCE=memory` (override `.env` khi compose nội suy) — khi `docker compose up` cần truyền `MARKET_DATA_SOURCE=auto` tường minh.
- Bật khóa bằng cách đặt `API_AUTH_KEY` trong `.env` rồi `docker compose up -d --force-recreate api`.

---

## Task: T017 — SSI FastConnect là nguồn chính (Yahoo dự phòng) + `/readyz` báo đúng thực tế

**Trạng thái:** HOÀN THÀNH (2026-09-27)
**Mục tiêu:** (a) đưa SSI FastConnect thành nguồn dữ liệu thị trường **chính** với chuỗi dự phòng tự động về Yahoo; (b) trả lời trung thực câu hỏi "hệ thống đã sẵn sàng chưa" ở `/readyz` (bỏ giá trị hardcode `pending`/`offline:…`).

### Các công việc đã thực hiện:
- [x] **Chuỗi nhà cung cấp** — `src/data/providers/registry.py::market_provider_chain(primary)`: nguồn chính trước, rồi `fallback_chains.market`, khử trùng lặp ⇒ `[ssix_finipro, yahoo, vndirect, tcbs, dsc]`; export qua `src/data/providers/__init__.py` + `src/data/__init__.py`.
- [x] **Dự phòng trong job EOD** — `apps/worker/main.py::scheduled_eod_ingestion()` đi hết chuỗi: nguồn không dựng được (thiếu credential) hoặc trả 0 dòng ⇒ log WARNING + thử nguồn kế tiếp; hết chuỗi ⇒ ERROR. `SCHEDULER_EOD_SOURCE` mặc định `ssix_finipro` (`apps/api/config.py`, `docker-compose.yml` ×2, `.env.example`).
- [x] **`/readyz` trung thực** — `apps/api/main.py`: `_database_status()` (connected / connected-no-prices / unreachable), `_qdrant_status()`, `_agents_status()` (`llm:<model>` | `offline:<tasks>`), `_market_source_status()` (`<chế độ>-><service>`), thêm khoá `market_source`; probe best-effort không ném 5xx.
- [x] **Qdrant trong image** — extra `[qdrant]` trong `pyproject.toml` (chỉ client, pin trùng `[rag]`), `docker/Dockerfile.api` + `Dockerfile.worker` cài `.[dev,ml,qdrant]`.
- [x] **Kiểm thử (+12)** — `test_sources_registry.py` (2), `test_worker_scheduler.py` (2), `test_api.py` (4), `test_deployment_config.py` (3, có test chống trôi pin).
- [x] **Tài liệu** — `docs/DATA_SOURCES_vi.md`, `docs/DEPLOYMENT_vi.md`, `docs/api.html`, `docs/status.html`, `docs/modules.html`, `docs/pipeline.html`, `helper/deployment_vi.md`, `helper/resources_vi.md`, `memory-bank/{changelog,decisions,known-issues,current-state,tasks,active-task}_vi.md`, `configs/sources.yaml` (`VERIFIED_2026-09-27`).

### Kiểm chứng trực tiếp (fact đã đo, 2026-09-27):
- `curl /readyz` → `{"status":"ready","market_source":"auto->db","dependencies":{"database":"connected","qdrant":"up","agents":"llm:qwen3.5"}}`
- `ingest --dataset prices --source ssix_finipro --symbols FPT,VCB,HPG,ACB --start 2026-09-01 --end 2026-09-26` → `fetched=68 written=68 issues=0 quality=93.74`
- `ingest --dataset index_prices --source ssix_finipro --indexes VNINDEX,VN30 --start 2026-09-01 --end 2026-09-26` → `fetched=34 written=34 quality=93.74`
- CSDL: 716 dòng `prices` (source `ssix_finipro`) · 34 dòng `index_prices`; Qdrant: collection `dtck_docs`, `GET /rag/status` → `qdrant_available: true`
- Suite: `LLM_PROVIDER=mock MARKET_DATA_SOURCE=memory pytest tests/unit -q` → **442 passed, 3 skipped**; `ruff` sạch; `mypy apps src` → 129 tệp sạch; `docker compose build api worker` thành công.

### Ghi chú vận hành:
- `docker compose build api worker` **bắt buộc** sau thay đổi này (Dockerfile + code job).
- Credential SSI: `SSI_CONSUMER_ID` + `SSI_CONSUMER_SECRET` trong `.env` (đổi JWT qua `Market/AccessToken`); `FINIPRO_ACCESS_TOKEN` có thể để trống.
- Nếu SSI hết hạn ngạch/lỗi, job tự chuyển Yahoo — không cần đổi cấu hình; log sẽ ghi `EOD source '…' … trying the next source`.

---

## Task: T016 — Nối tầng suy luận LLM local (Ollama) cho Analysis Agent

**Trạng thái:** HOÀN THÀNH (2026-09-26)
**Mục tiêu:** Cho Analysis Agent sinh `thesis` tiếng Việt từ Ollama `qwen3.5` (ADR-005) **không** đổi dữ liệu quant, có fallback tất định, và giữ nguyên bộ test offline.

### Các công việc đã thực hiện:
- [x] **Tầng provider LLM** — tạo `src/agents/llm/` (`LLMClient` Protocol `@runtime_checkable`, `MockLLMClient`, `OllamaLLMClient` dùng `httpx` + `transport` để test không cần mạng, `create_llm_client`).
- [x] **Nối vào agent** — `AnalysisAgent(llm=...)` + `_synthesize_llm_thesis()` (prompt gồm điểm đa yếu tố, điểm thành phần, giá, regime, catalysts, risks, tin tức; chỉ thay `thesis`; lỗi/timeout/rỗng ⟶ mẫu tất định); `Orchestrator(llm=...)` truyền xuống và gắn nhãn audit `deterministic-quant-v1+<model>`.
- [x] **Cấu hình** — `get_llm_client()` trong `apps/api/services/agent_service.py` (`mock` ⇒ `None`), `timeout_s = LLM_TIMEOUT_SECONDS + 15`, thêm `llm_think` vào `Settings` + `.env.example`/`.env` (`LLM_THINK=false`), ví dụ `local`/`qwen3.5`/`host.docker.internal:11434`.
- [x] **API** — `GET /api/v1/agents` trả thêm `llm_model` + `reasoning`.
- [x] **Test** — `tests/unit/test_llm_client.py` (22 test), `test_smoke` nhận alias `ollama`.
- [x] **Tài liệu** — `docs/AGENT_ARCHITECTURE_vi.md` §8.1, `docs/api.html`, `docs/modules.html`, `docs/index.html`, `docs/structure.html`, `docs/DEPLOYMENT_vi.md`, `helper/deployment_vi.md`, `helper/resources_vi.md`, `memory-bank/{changelog,tasks,current-state}_vi.md`.
- [x] **Kiểm chứng trực tiếp** — rebuild image `api` → `docker compose up -d api`; từ host: `POST /api/v1/agents/analyze` `VCB` `succeeded` `latency_ms≈15000` `model=deterministic-quant-v1+qwen3.5`; async `HPG` `succeeded` 12,1 s; bộ test `LLM_PROVIDER=mock MARKET_DATA_SOURCE=memory pytest` → **449 passed, 3 skipped, 1 failed có sẵn**; `ruff` + `mypy` (129 tệp) sạch.

### Ghi chú vận hành (fact đã đo):
- Ollama máy host đã `OLLAMA_HOST=0.0.0.0` (systemd override) → container qua `host.docker.internal:11434` OK.
- `think=false` **bắt buộc** với `qwen3.5`: nếu bật, khối suy luận chiếm hết `num_predict` nên `response` rỗng và mất 30–170 s. Với `think=false`: ~12–22 s/luận điểm.
- `qwen2.5-7b-65k:latest` (~5–11 s) là lựa chọn nhanh hơn nếu cần độ trễ thấp hơn.
- Lỗi có sẵn ngoài phạm vi: `tests/integration/test_scoring_job::test_api_reader_serves_the_persisted_run` (`0.9999` vs `1.0`).

---

## Task trước: Chuẩn hóa 100% tài liệu tiếng Việt — Xóa bỏ các bản tiếng Anh & Ban hành quy ước tài liệu tiếng Việt

**Trạng thái:** HOÀN THÀNH (2026-09-26)
**Quy ước bắt buộc mới:** Từ bây giờ khi cập nhật các file markdown của project chỉ sử dụng tiếng Việt và các file tiếng Việt. Toàn bộ các file tiếng Anh tương ứng đã bị xóa bỏ để đảm bảo tính duy nhất và nhất quán của tài liệu.

### Các công việc đã thực hiện:
- [x] **Rà soát toàn bộ tệp markdown**: Kiểm tra và xác nhận mọi tài liệu trong `docs/`, `helper/`, `memory-bank/`, `configs/`, `database/migrations/`, `notebooks/`, `offline_package/`, `scripts/` và `README.md` đều có đầy đủ nội dung bằng tiếng Việt.
- [x] **Xóa bỏ các file trùng lặp / thừa**:
  - Xóa 2 bản thảo trùng lặp ở thư mục gốc: `AI powered Investment.md` và `SYSTEM_SPECIFICATION.md v1.0.md` (nội dung chuẩn đã có trong `docs/AI_INVESTMENT_CONCEPT.md` và `docs/SYSTEM_SPECIFICATION.md`).
  - Xóa toàn bộ 22 file tiếng Anh đã có bản tiếng Việt tương ứng:
    - `docs/` (12 file): `AGENT_ARCHITECTURE.md`, `API_SPECIFICATION.md`, `ARCHITECTURE.md`, `BACKTESTING.md`, `DATABASE_SCHEMA.md`, `DATA_ARCHITECTURE.md`, `DATA_SOURCES.md`, `DEPLOYMENT.md`, `ML_ARCHITECTURE.md`, `QUANT_ENGINE.md`, `RAG_ARCHITECTURE.md`, `SECURITY.md`.
    - `helper/` (2 file): `deployment.md`, `resources.md`.
    - `memory-bank/` (8 file): `active-task.md`, `architecture-decisions.md`, `changelog.md`, `current-state.md`, `decisions.md`, `known-issues.md`, `project-context.md`, `tasks.md`.
- [x] **Việt hóa các README phụ trợ**:
  - `README.md` gốc repo được viết lại 100% bằng tiếng Việt.
  - `configs/README.md`, `database/migrations/README.md`, `notebooks/README.md`, `offline_package/README.md`, `scripts/README.md` đã được dịch sang tiếng Việt hoàn chỉnh.
- [x] **Làm sạch các thông báo nguồn trôi lệch**:
  - Gỡ bỏ hoàn toàn các câu chú thích `> Bản gốc tiếng Anh: ...` và `> Bản tiếng Anh là nguồn chính thức` khỏi header của các file `*_vi.md` trong `docs/`, `helper/`, `memory-bank/`.
  - Cập nhật tài liệu tham chiếu trong `docs/status.html`, `helper/deployment_vi.md`, `memory-bank/project-context_vi.md`, `current-state_vi.md`, `tasks_vi.md` và `changelog_vi.md`.
- [x] **Ghi nhớ vào Memory Bank**:
  - Ban hành và ghi nhận quy tắc cốt lõi: Tài liệu dự án từ nay vận hành 100% bằng tiếng Việt trên các file tiếng Việt.
- [x] **Kiểm chứng hệ thống**:
  - Chạy `pytest`, `ruff check .`, `mypy` để đảm bảo không có bất kỳ regression hoặc đứt gãy nào.

---

## Task trước: Lộ trình triển khai tuần tự — Nối dữ liệu thật cho Dashboard & trang RAG (Option 1), Scheduler worker nền (Option 2), Provider EOD công khai cho thị trường Việt Nam (Option 3)


**Trạng thái:** ĐANG TRIỂN KHAI
**Bước hiện tại:** Option 3 (Provider EOD công khai) — triển khai + kiểm chứng xong

### Kế hoạch thực hiện:

- [x] **Bước 1: Nối dữ liệu thật cho Dashboard & trang RAG (Option 1)**
  - [x] Phân tích fallback và phong bì phân trang của DashboardClient.
  - [x] Cập nhật `apps/dashboard/client.py`:
    - Cho `list_stocks()`, `get_news()`, `get_backtests()` mở phong bì phân trang `{"items": [...]}` do FastAPI trả về (`/api/v1/stocks`, `/api/v1/news`, `/api/v1/backtests`) mà vẫn giữ tương thích list cho fallback ngoại tuyến.
    - Thêm phương thức cho tìm kiếm RAG (`search_rag(query, symbol=None, top_k=5)`), trạng thái RAG (`get_rag_status()`) và liệt kê bằng chứng (`get_evidence(query, symbol=None, top_k=5)`).
  - [x] Cập nhật `apps/dashboard/components.py`:
    - Thêm helper trình bày cho bằng chứng và mục RAG (ví dụ `evidence_rows()`, định dạng điểm, nhãn tin cậy).
  - [x] Cập nhật `apps/dashboard/app.py`:
    - Thêm trang "📰 Tin tức & RAG" (xem tin mới nạp, lọc theo mã/nguồn, tìm kiếm ngữ nghĩa tương tác kèm trích dẫn/đoạn bằng chứng).
  - [x] Cập nhật `tests/unit/test_dashboard.py` với unit test đầy đủ cho việc mở phong bì phân trang, gọi client RAG và helper trình bày.

- [x] **Bước 2: Job nền APScheduler cho worker (Option 2)**
  - [x] Cấu hình job định kỳ trong `apps/worker/main.py`:
    - Nạp tin tức định kỳ (mỗi 15–30 phút qua provider `cafef` / dự phòng).
    - Job chấm điểm hệ số EOD hằng ngày sau giờ đóng cửa (ví dụ 15:30 giờ VN các ngày trong tuần).
  - [x] Thêm test cho cấu hình job của scheduler.

- [x] **Bước 3: Provider dữ liệu EOD công khai cho thị trường Việt Nam (Option 3)**
  - [x] Triển khai provider EOD công khai tuân theo `DataProvider`
        (`src/data/providers/yahoo_chart.py` — `YahooChartProvider`, lớp con của
        `HttpJsonProvider`; chỉ override `_build_request` + `_map_rows`).
  - [x] Nối vào `configs/sources.yaml` (`yahoo`, priority 85,
        `endpoints_status: VERIFIED_2026-09-25`) và `create_provider`
        (dispatch `endpoints.eod.client: yahoo_chart`); chuỗi dự phòng thị trường
        nay là `[yahoo, vndirect, tcbs, dsc]`.
  - [x] Job `daily_eod_ingestion` cho worker (Thứ 2–6 15:05 ICT, trước scoring
        15:30) + các setting (`scheduler_eod_source/cron_hour/cron_minute/lookback_days`).
  - [x] Unit test: `tests/unit/test_yahoo_chart_provider.py` (13 test,
        fixture đã ghi `tests/fixtures/yahoo_chart_sample.json` gồm sự kiện tách
        FPT 11:10 ngày 2026-09-21), test scheduler mở rộng lên 7.

### Option 3 — Kiểm chứng (2026-09-25):

- `LLM_PROVIDER=mock pytest` → **422 passed, 3 skipped**; `ruff check .` sạch; `mypy` sạch (126 tệp).
- Trực tiếp: `DTCK_LIVE_TESTS=1 pytest -m live` → **2 passed** (Yahoo + CaféF).
- Nạp end-to-end (worker CLI, TimescaleDB dev): `ingest --dataset prices
  --source yahoo --symbols FPT,VCB,HPG,ACB --start 2026-09-01 --end 2026-09-25`
  → **fetched=62 written=62 skipped=0 issues=0 quality=94.88** (đạt cổng);
  đã xác nhận in giá thô chưa điều chỉnh trong `prices` (FPT 2026-09-03 close 72200,
  source=yahoo); FPT có 14 dòng so với 16 của các mã khác (các ngày placeholder
  volume 0 vắng mặt một cách trung thực). `compute-scores --lookback 60` → scored=4 mã thật.
- Lưu ý đã biết (ghi trong `configs/sources.yaml` + `docs/DATA_SOURCES.md` §8):
  `trading_value` = xấp xỉ close × volume (Yahoo không có trường turnover);
  un-adjust tách qua `events=split`; `meta.fullExchangeName` không dùng được
  (nhãn `exchange` trong config chỉ mang tính gắn nhãn — `prices` khoá theo `stock_id`).
- Lỗi tồn tại từ trước, không liên quan task này: `test_smoke.py::test_api_config_loads`
  từ chối `LLM_PROVIDER=ollama` trong `.env` cục bộ (chạy bộ test với `LLM_PROVIDER=mock`).
  → *Đã hết ở T016 (2026-09-26): allowlist của smoke test nhận thêm `ollama` như alias của `local`.*


## Workstream W1, W1b, W2: đường đọc CSDL, chấm điểm hệ số quant, nạp tin CaféF RSS (2026-09-25)

**Trạng thái:** HOÀN THÀNH
**Mục tiêu:** Nối đường đọc FastAPI vào TimescaleDB (W1), triển khai job chấm điểm hệ số quant hằng ngày (W1b), và nối nạp tin trực tiếp từ CaféF RSS không cần chứng thực bên ngoài (W2).

### Sản phẩm & kiểm chứng:

- [x] **W1 (đường đọc CSDL)**:
  - Tạo protocol `apps/api/services/market_source.py` + `DbMarketService` trong `apps/api/services/db_market.py`.
  - Thêm `ranking_payload.py` để tách việc chuyển đổi lược đồ xếp hạng khỏi nguồn trong bộ nhớ so với CSDL.
  - Cấu hình `MARKET_DATA_SOURCE=memory|db|auto` trong `apps/api/dependencies.py` và `apps/api/config.py`.
  - Cập nhật router (`fundamentals`, `valuation`, `technical`, `news`) để dùng `MarketSource`.
  - Unit test: `tests/unit/test_market_data_source.py`.
  - Integration test: `tests/integration/test_db_market.py` chạy với PostgreSQL/TimescaleDB thật.
- [x] **W1b (job chấm điểm)**:
  - Tạo `src/quant/scoring/job.py` tính các hệ số thô từ giá (RSI-14, động lượng 63 ngày, đảo dấu độ biến động 20 ngày) và upsert vào `factor_scores` với giá trị `NULL` trung thực cho các chiều chưa có dữ liệu.
  - Thêm lệnh `compute-scores` vào `apps/worker/cli.py`.
  - Unit test: `tests/unit/test_scoring_job.py`.
  - Integration test: `tests/integration/test_scoring_job.py`.
- [x] **W2 (provider CaféF RSS & liên kết mã cho tin)**:
  - Ghi fixture XML thật (`tests/fixtures/cafef_rss_sample.xml`).
  - Triển khai parser RSS/Atom bằng thư viện chuẩn và `RssNewsProvider` trong `src/data/providers/rss.py`.
  - Đăng ký provider `cafef` trong `configs/sources.yaml` (`VERIFIED_2026-09-25`) và `src/data/providers/registry.py`.
  - Hỗ trợ trích nhiều mã và lọc theo mã trong `src/rag/ingestion/chunking.py` và `src/rag/retrieval/store.py`.
  - Nối khớp mã vào phần nạp tin của worker (`apps/worker/cli.py`).
  - Unit test: `tests/unit/test_rss_provider.py` (MockTransport + parse fixture XML + xử lý ngày tháng).
  - Kiểm chứng trực tiếp: nạp 50 bài thật từ CaféF; xác nhận lưu trong `news` và liên kết trong `news_symbols`; kiểm chứng `/api/v1/news`, `/api/v1/rag/search` và `/api/v1/evidence`.
- [x] **Cổng chất lượng**:
  - `ruff check .` -> All checks passed!
  - `mypy` -> Success: no issues found in 125 source files.
  - `pytest` -> 399 passed, 2 skipped trong ~3.0s.

## Task trước đó

**Trạng thái:** HOÀN THÀNH
**Mục tiêu:** API khởi động với phụ thuộc ML tái lập được trong Docker; giữ các import ML công khai.
**Phạm vi:** Dockerfile API/worker, export ML lazy, test hồi quy và tài liệu triển khai.
**Ràng buộc:** Giữ nguyên các sửa đổi Compose sẵn có và volume CSDL; dùng extra `[ml]` sẵn có.

- [x] Build image API/worker: `BUILD_EXIT_CODE=0`.
- [x] Chỉ tạo lại API/worker bằng `docker compose up -d --no-deps api worker`.
- [x] API import được sklearn 1.9.1, xgboost 2.1.4, lightgbm 4.7.0; worker import được `ModelTrainer`.
- [x] `/healthz` và `/api/v1/predictions/VNM` trong container trả HTTP 200.
- [x] Lint, kiểu và test hồi quy (bao gồm import ML tuỳ chọn bị chặn).
  - `ruff check .` sạch · `mypy src apps` sạch (119 tệp) · `pytest tests/unit` **343 passed, 1 skipped**
    (chạy với `LLM_PROVIDER=mock`; `.env` cục bộ đặt `ollama` và bị allowlist của smoke test từ chối)
  - Trong container: `import sklearn` → 1.9.1; smoke test import-bị-chặn chứng minh `apps.api.main`
    import được mà không cần sklearn và `src.ml.training` vẫn lazy.

---

**ID:** `T014 — ML prediction: feature dataset + training + calibration + registry + predictions API (Phase 6)`
**Trạng thái:** HOÀN THÀNH phần mã nguồn (2026-09-16); huấn luyện trên dữ liệu thật chờ KI-012

**Mục tiêu:** Dự đoán huấn luyện cổ điển theo đặc tả §14/§15/§26/§40 + `docs/ML_ARCHITECTURE.md`: dataset đặc trưng as-of (không rò rỉ), huấn luyện XGBoost với chia theo thời gian, hiệu chuẩn kiểu Platt, registry model có vòng đời phiên bản, endpoint `/api/v1/predictions`, CLI `train-model` cho worker.

**Phạm vi:** `src/ml/` (feature_dataset, training, model_registry, predictor, schemas), `apps/api/routers/predictions.py`, `apps/worker/cli.py` (train-model), `tests/unit/test_ml_*.py`, `test_t014_t015.py`.

**Ràng buộc:** Tất định, ưu tiên ngoại tuyến; tương thích sklearn 1.8+ (không dùng `CalibratedClassifierCV cv="prefit"`); không rò rỉ mục tiêu trong đặc trưng.

**Sửa lỗi chính trong lúc triển khai:**

- **Loại bỏ rò rỉ mục tiêu:** cột lợi nhuận tương lai `horizon_return_*` từng nằm trong ma trận đặc trưng (`horizon_return_5d` == mục tiêu đúng nghĩa); đã xoá khỏi đặc trưng, chỉ giữ trong mục tiêu. Test hồi quy chứng minh đặc trưng bất biến với cú sốc giá tương lai.
- **Lỗi chia theo ngày trùng:** chia theo thời gian từng dùng số dòng; một ngày có thể rơi vào hai phần. Nay chia theo ngày giao dịch duy nhất; có chốt chặn từ chối phần chỉ có một lớp, khung lệch và nhãn không phải 0/1.
- **Đặc trưng mã bằng `hash()`** bị ngẫu nhiên hoá theo tiến trình (PYTHONHASHSEED) → thay bằng `zlib.crc32`.
- **KI-012 (mới):** fixture thị trường tổng hợp tăng đơn điệu → 100% nhãn 5 ngày dương; không thể fit classifier thật. `train()`/`train-model` báo lỗi to thay vì phát ra model giả; predictor phục vụ stub dự phòng tất định. Huấn luyện thật chờ nối CSDL (KI-006/007/008).
  - *Cập nhật 2026-09-25:* đường đọc CSDL đã có (`DbMarketService`); lối mở là thêm cờ `--source db` cho `train-model` (xem `tasks_vi.md`).

**Nghiệm thu:**

- [x] `ruff check .` sạch
- [x] `mypy` sạch — "Success: no issues found in 119 source files"
- [x] `pytest -q` — **325 passed** (+12 test ML/API; rò rỉ + hợp đồng huấn luyện)
- [x] `docs/status.html` đã cập nhật (ML 80%, KI-012, roadmap → T015)
- [x] memory bank đã cập nhật (active-task/current-state/changelog/tasks)

