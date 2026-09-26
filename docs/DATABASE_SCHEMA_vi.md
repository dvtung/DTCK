# SCHEMA CƠ SỞ DỮ LIỆU (Bản tiếng Việt)

## Nền tảng Nghiên cứu & Quyết định Đầu tư AI

> Thuật ngữ chuyên môn (tên bảng, tên cột, kiểu dữ liệu) giữ nguyên tiếng Anh.

**Phiên bản:** 1.0
**Trạng thái:** Dự thảo — suy ra từ SYSTEM_SPECIFICATION.md v1.0
**Kho chính:** PostgreSQL + extension TimescaleDB
**Kho vector:** Qdrant (xem RAG_ARCHITECTURE.md — không trình bày ở đây)

---

# 1. Nguyên tắc thiết kế

1. Mọi bảng mang dữ liệu chuỗi thời gian thị trường/quant phải là **hypertable TimescaleDB** phân vùng theo cột timestamp.
2. Mọi giá trị suy ra (đặc trưng, điểm, tín hiệu, dự báo) phải truy vết được về `data_version` / `feature_version` / `model_version`.
3. Không bảng nào được **sửa ngược sự thật lịch sử** đã dùng tính đặc trưng (append-only nếu có thể; điều chỉnh là dòng mới, không UPDATE, trừ luồng điều chỉnh `is_latest` tường minh).
4. Mọi bảng có `created_at timestamptz` và, nếu sửa được, `updated_at timestamptz`.
5. Mã là khóa nối tự nhiên: `symbol` (ticker) + `exchange` định danh duy nhất một công cụ niêm yết theo thời gian (xử lý hủy/tái niêm yết qua lịch sử `stocks`).
6. Khóa ngoại ép ở tầng CSDL. Hiệu lực nghiệp vụ mềm (định ngày hiệu lực lưỡng thời) xử lý qua `valid_from` / `valid_to` trên bảng biến đổi chậm (vd báo cáo tài chính điều chỉnh).

---

# 2. Tổng quan schema (Miền → Bảng)

```text
Tham chiếu      : stocks, exchanges, sectors, industries
Dữ liệu thị trường: prices, adjusted_prices, index_prices, foreign_flows, prop_trading_flows
Dữ liệu cơ bản  : financial_statements, financial_ratios
Sự kiện doanh nghiệp: corporate_events
Tin tức         : news, news_symbols
Dữ liệu vĩ mô   : macro_indicators
Quant           : features, factor_scores, signals, market_regimes
ML              : ml_models, predictions, prediction_evaluations
Backtesting     : backtests, backtest_trades, backtest_metrics
RAG / Bằng chứng: documents (chỉ metadata; vector nằm ở Qdrant), evidence
Agent           : agent_runs, agent_tool_calls
Danh mục        : portfolios, portfolio_positions, portfolio_snapshots
Quản trị/Kiểm toán: model_registry, agent_registry, audit_logs, data_quality_scores
Người dùng/Auth : users, api_keys, roles
```

---

# 3. Bảng tham chiếu

## 3.1. `exchanges`

| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | smallserial PK | |
| code | text UNIQUE | `HOSE`, `HNX`, `UPCOM` |
| name | text | |

## 3.2. `sectors` / `industries`

| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | serial PK | |
| code | text UNIQUE | mã ICB hoặc taxonomy tự định |
| name | text | |
| parent_id | int FK → sectors.id | nullable, để cuộn industry → sector |

## 3.3. `stocks`

| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | serial PK | |
| symbol | text | vd `FPT` |
| exchange_id | smallint FK → exchanges.id | |
| company_name | text | |
| sector_id | int FK → sectors.id | |
| industry_id | int FK → industries.id | |
| listed_date | date | |
| delisted_date | date | nullable |
| status | text | `ACTIVE`, `DELISTED`, `SUSPENDED` |
| is_vn30 | boolean | cờ universe MVP |
| is_vn100 | boolean | |
| created_at | timestamptz | |
| updated_at | timestamptz | |

`UNIQUE (symbol, exchange_id)`. Mã hủy niêm yết **giữ lại** (không bao giờ xóa) để chống thiên lệch sống sót (§17 đặc tả).

---

# 4. Dữ liệu thị trường (Hypertable TimescaleDB)

## 4.1. `prices` (OHLCV thô, hypertable theo `trade_date`)

| Cột | Kiểu | Ghi chú |
|---|---|---|
| stock_id | int FK → stocks.id | |
| trade_date | date | một phần PK (`stock_id, trade_date`) |
| open | numeric(18,4) | |
| high | numeric(18,4) | |
| low | numeric(18,4) | |
| close | numeric(18,4) | chưa điều chỉnh |
| volume | bigint | |
| trading_value | numeric(24,2) | giá trị khớp (VND) |
| market_cap | numeric(24,2) | nullable |
| source | text | vd `ssix_finipro`, `yahoo` |
| ingested_at | timestamptz | |

## 4.2. `adjusted_prices` (hypertable theo `trade_date`)

| Cột | Kiểu | Ghi chú |
|---|---|---|
| stock_id | int FK | |
| trade_date | date | |
| adj_factor | numeric(18,8) | tích lũy tách/gộp, cổ tức tiền mặt |
| adj_close | numeric(18,4) | |

Dữ liệu thô không bao giờ sửa — hệ số hiệu chỉnh version.

> Thực tế triển khai 2026-09-25: Yahoo trả giá đã điều chỉnh tách nên provider
> un-adjust qua `events=split` để `prices.close` khớp giá giao dịch thật;
> `trading_value` ≈ close × volume (Yahoo không có trường turnover).

## 4.3. `index_prices` (hypertable theo `trade_date`)

| Cột | Kiểu | Ghi chú |
|---|---|---|
| index_code | text | vd `VNINDEX`, `VN30` |
| trade_date | date | |
| open/high/low/close | numeric(18,4) | |
| volume | bigint | |
| trading_value | numeric(24,2) | |

## 4.4. `foreign_flows` / `prop_trading_flows` (hypertable theo `trade_date`)

| Cột | Kiểu | Ghi chú |
|---|---|---|
| stock_id | int FK (nullable — có thể là dòng cấp thị trường) | |
| trade_date | date | |
| buy_value | numeric(24,2) | |
| sell_value | numeric(24,2) | |
| net_value | numeric(24,2) | tiền vào ròng |
| desk | text | `FOREIGN` / `PROP` |

---

# 5. Dữ liệu cơ bản

## 5.1. `financial_statements` — lưỡng thời, không bao giờ ghi đè (§5.1, §17)

| Cột | Kiểu | Ghi chú |
|---|---|---|
| stock_id | int FK | |
| period_type | text | `Q` / `Y` |
| period_end | date | cuối kỳ báo cáo |
| report_date | date | ngày nộp/công bố (có thể > period_end nhiều) |
| line_item | text | vd `revenue`, `net_profit`, `equity` |
| value | numeric(24,4) | |
| unit | text | `VND` / `%` / … |
| valid_from | timestamptz | khi sự thật này thành hiện hành |
| valid_to | timestamptz | nullable; dòng điều chỉnh đóng dòng cũ |
| is_latest | boolean | |

Truy vấn as-of bắt buộc: `WHERE :as_of >= valid_from AND (:as_of < valid_to OR valid_to IS NULL)` —
backtester không bao giờ được thấy số điều chỉnh trước `report_date` (§17).

## 5.2. `financial_ratios` — tính trước từ báo cáo đã chốt

| Cột | Kiểu | Ghi chú |
|---|---|---|
| stock_id | int FK | |
| period_end | date | |
| pe_ttm/pe_forward/pb/ev_ebitda/ev_sales/dividend_yield/peg | numeric | nullable |
| roe_ttm/roa_ttm/gross_margin/op_margin/net_margin | numeric | nullable |
| debt_to_equity/interest_coverage | numeric | nullable |

---

# 6. Snapshot định giá

## 6.1. `valuation_daily` (hypertable theo `trade_date`)

| Cột | Kiểu | Ghi chú |
|---|---|---|
| stock_id | int FK | |
| trade_date | date | |
| pe_ttm/pe_forward/pb/ev_ebitda/ev_sales/dividend_yield/peg | numeric | nullable |
| industry_pe_median/industry_pb_median | numeric | nullable — phân vị ngành |
| hist_pe_p20_p80 | numeric[] | dải lịch sử |
| computed_at | timestamptz | |

---

# 7. Sự kiện doanh nghiệp & tin tức

## 7.1. `corporate_events`

| Cột | Kiểu | Ghi chú |
|---|---|---|
| stock_id | int FK | |
| event_type | text | `EARNINGS`, `DIVIDEND`, `SPLIT`, `RIGHTS`, `AGM`, `MA`, `LEGAL` |
| event_date | date | |
| ex_date | date | nullable |
| payload | jsonb | hệ số tách, cổ tức/cổ phiếu, … |
| source | text | |

## 7.2. `news` + `news_symbols`

| Cột | Kiểu | Ghi chú |
|---|---|---|
| source | text | `cafef`, `vnexpress`, `vietstock`, … |
| title | text | |
| url | text UNIQUE | |
| published_at | timestamptz | |
| content | text | |
| sentiment | numeric(-1..1) | nullable |
| importance | numeric(0..1) | nullable |

`news_symbols(news_id, stock_id, relevance)` — khử trùng `(source, title)`.

> Thực tế 2026-09-25: parser RSS stdlib (`RssNewsProvider`), đã nạp 50 bài CaféF thật,
> chunking hỗ trợ đa mã (`news_symbols` nhiều dòng một bài).

---

# 8. Dữ liệu vĩ mô

## 8.1. `macro_indicators` (hypertable theo `period_date`)

| Cột | Kiểu | Ghi chú |
|---|---|---|
| code | text | vd `GDP_QOQ`, `CPI_YOY`, `POLICY_RATE`, `USDVND` |
| period_date | date | |
| value | numeric | |
| unit | text | |
| source | text | `SBV`, `GSO`, `IMF`, … |

---

# 9. Đầu ra Quant Engine

## 9.1. `features` (hypertable theo `trade_date`)

| Cột | Kiểu | Ghi chú |
|---|---|---|
| stock_id | int FK | |
| trade_date | date | |
| feature_version | text | vd `technical_1.0` |
| name | text | tên đặc trưng |
| value | numeric | |

## 9.2. `factor_scores` (hypertable theo `trade_date`)

| Cột | Kiểu | Ghi chú |
|---|---|---|
| stock_id | int FK | |
| trade_date | date | |
| scoring_version | text | vd `baseline_1.0` (trọng số §12) |
| technical_score/fundamental_score/valuation_score/momentum_score/quality_score/risk_score | numeric(5,2) | nullable — NULL trung thực khi thiếu chiều |
| overall_score | numeric(5,2) | tổng có chuẩn hóa lại (§12, hợp đồng phân rã) |

`UNIQUE (stock_id, trade_date, scoring_version)` — `compute-scores` upsert idempotent.

> Thực tế 2026-09-25: job `src/quant/scoring/job.py` tính RSI-14, momentum 63 ngày,
> −biến động 20 ngày từ giá thô; đã chạy trên 4 mã thật.

## 9.3. `signals` (hypertable theo `trade_date`)

| Cột | Kiểu | Ghi chú |
|---|---|---|
| stock_id | int FK | |
| trade_date | date | |
| signal_type | text | vd `RANKING`, `RISK_ALERT` |
| signal | text | `POSITIVE` / `NEUTRAL` / `NEGATIVE` |
| score | numeric(5,2) | |
| scoring_version | text | |

## 9.4. `market_regimes` (hypertable theo `trade_date`)

| Cột | Kiểu | Ghi chú |
|---|---|---|
| trade_date | date PK | |
| regime | text | `BULL`, `SIDEWAYS`, `BEAR`, `HIGH_VOLATILITY`, `CRISIS` |
| confidence | numeric(3,2) | |

---

# 10. Học máy

## 10.1. `ml_models` — bản sao registry (§40)

| Cột | Kiểu | Ghi chú |
|---|---|---|
| model_id | text | vd `price_direction_xgb` |
| version | text | |
| algorithm | text | `xgboost`, `lightgbm`, … |
| training_data_version | text | |
| feature_version | text | |
| train_start/train_end/val_start/val_end/test_start/test_end | date | cửa sổ thời gian |
| metrics | jsonb | accuracy/auc/f1 + CAGR/Sharpe/… |
| params | jsonb | siêu tham số |
| status | text | `EXPERIMENTAL`, `VALIDATING`, `APPROVED`, `PRODUCTION`, `DEPRECATED` |

> Thực tế: `train-model` hiện từ chối trung thực trên fixture chỉ tăng (KI-012);
> huấn luyện thật chờ dữ liệu giá hỗn hợp (xem DEPLOYMENT_vi bước 3.2 + backfill KI-009).

## 10.2. `predictions` (hypertable theo `trade_date`)

| Cột | Kiểu | Ghi chú |
|---|---|---|
| stock_id | int FK | |
| trade_date | date | ngày sinh dự báo |
| model_id/model_version/feature_version | text | |
| target | text | vd `return_gt_0` |
| predicted_value | numeric | xác suất/giá trị |
| horizon_days | int | chân trời khai báo (§6) |

## 10.3. `prediction_evaluations`

| Cột | Kiểu | Ghi chú |
|---|---|---|
| prediction_id | bigint FK | |
| actual_outcome | numeric | kết quả thực khi hết chân trời |
| error | numeric | |
| hit | boolean | |

---

# 11. Backtesting

## 11.1. `backtests`

| Cột | Kiểu | Ghi chú |
|---|---|---|
| name | text | |
| strategy_config | jsonb | universe, tái cân bằng, cỡ vị thế |
| start_date/end_date | date | |
| initial_capital | numeric(24,2) | |
| commission_bps/slippage_bps | numeric | |
| run_type | text | `IN_SAMPLE`, `OUT_OF_SAMPLE`, `WALK_FORWARD`, `ROLLING` |
| status | text | |

## 11.2. `backtest_trades`

| Cột | Kiểu | Ghi chú |
|---|---|---|
| backtest_id | bigint FK | |
| stock_id | int FK | |
| side | text | `BUY` / `SELL` |
| quantity | numeric | thoát một phần chỉ ghi lượng đã bán |
| price | numeric(18,4) | |
| trade_date | date | khớp ở mở cửa `t+1` (không nhìn trước) |
| pnl | numeric(24,2) | nullable cho lệnh vào |

## 11.3. `backtest_metrics`

| Cột | Kiểu | Ghi chú |
|---|---|---|
| backtest_id | bigint FK | |
| metric | text | CAGR/Sharpe/Sortino/Calmar/MaxDD/WinRate/… (§15) |
| value | numeric(18,6) | |

---

# 12. RAG / Bằng chứng

## 12.1. `documents` — chỉ metadata (vector nằm ở Qdrant)

| Cột | Kiểu | Ghi chú |
|---|---|---|
| doc_type | text | `news`, `report`, `filing`, … |
| source | text | |
| title | text | |
| url | text | |
| published_at | timestamptz | |
| qdrant_point_id | uuid | liên kết tới point Qdrant |
| storage_path | text | nullable — blob thô (object storage sau, §19 mở) |

## 12.2. `evidence` (§19 Evidence Engine)

| Cột | Kiểu | Ghi chú |
|---|---|---|
| claim | text | khẳng định được chứng minh |
| source | text | |
| source_type | text | vd `financial_report` |
| published_at | timestamptz | |
| data_timestamp | timestamptz | |
| evidence_text | text | đoạn trích |
| confidence | numeric(3,2) | |
| linked_entity_type/linked_entity_id | text | đa hình → Analysis/Prediction/Agent run/Report |

---

# 13. Agent (§20 / §41 Quản trị Agent)

## 13.1. `agent_runs` (§31)

| Cột | Kiểu | Ghi chú |
|---|---|---|
| agent_name | text | research/analysis/monitoring/portfolio/orchestrator |
| model | text | model + phiên bản (vd `mock/offline`) |
| prompt_version | text | |
| user_request | text | |
| final_output | jsonb | schema `InvestmentAnalysis` (§23) |
| status | text | `SUCCESS`, `FAILED`, `TIMEOUT` |
| latency_ms | int | |
| token_usage | jsonb | |

## 13.2. `agent_tool_calls` (§22)

| Cột | Kiểu | Ghi chú |
|---|---|---|
| run_id | bigint FK | |
| tool_name | text | |
| input | jsonb | |
| output | jsonb | |

`agent_registry` (bảng quản trị §41): phiên bản agent, phiên bản prompt, tool,
dữ liệu cho phép, schema output, điểm đánh giá, trạng thái.

---

# 14. Danh mục

## 14.1. `portfolios`

| Cột | Kiểu | Ghi chú |
|---|---|---|
| name | text | |
| base_currency | text | `VND` |
| created_at | timestamptz | |

## 14.2. `portfolio_positions`

| Cột | Kiểu | Ghi chú |
|---|---|---|
| portfolio_id | int FK | |
| stock_id | int FK | |
| quantity | numeric(18,4) | |
| avg_cost | numeric(18,4) | giá vốn bình quân |

## 14.3. `portfolio_snapshots` (hypertable theo `snapshot_date`)

| Cột | Kiểu | Ghi chú |
|---|---|---|
| portfolio_id | int FK | |
| snapshot_date | date | |
| total_value | numeric(24,2) | |
| cash | numeric(24,2) | |
| invested_value | numeric(24,2) | |
| pnl_total/pnl_day | numeric(24,2) | |
| return_total/return_day | numeric(10,6) | |
| max_drawdown | numeric(10,6) | |
| sector_exposure | jsonb | |
| concentration | numeric(10,6) | |

`PRIMARY KEY (portfolio_id, snapshot_date)`, hypertable.

---

# 15. Quản trị, kiểm toán, chất lượng dữ liệu

## 15.1. `audit_logs` — chỉ ghi thêm (§31, §41)

| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | bigserial PK | |
| entity_type | text | vd `agent_run`, `model`, `prediction` |
| entity_id | text | |
| action | text | |
| actor | text | user hoặc system |
| payload | jsonb | |
| created_at | timestamptz | |

Role ứng dụng **không có quyền UPDATE/DELETE** trên bảng này — cấm agent xóa audit log (§41).

## 15.2. `data_quality_scores` (§39 Khung chất lượng dữ liệu)

| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | bigserial PK | |
| dataset | text | vd `prices`, `financial_statements` |
| stock_id | int FK | nullable, dataset có thể toàn cục |
| as_of_date | date | |
| completeness | numeric(5,2) | |
| accuracy | numeric(5,2) | |
| consistency | numeric(5,2) | |
| freshness | numeric(5,2) | |
| uniqueness | numeric(5,2) | |
| validity | numeric(5,2) | |
| overall_score | numeric(5,2) | 0-100 (§39) |
| below_threshold | boolean | chặn dùng downstream khi true |

---

# 16. Người dùng / Auth (phase Production)

## 16.1. `users`

| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | uuid PK | |
| email | text UNIQUE | |
| password_hash | text | |
| role | text | `ADMIN`, `ANALYST`, `VIEWER` |
| created_at | timestamptz | |

## 16.2. `api_keys`

| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK | |
| key_hash | text | không bao giờ lưu key thô |
| scopes | jsonb | |
| created_at | timestamptz | |
| revoked_at | timestamptz | nullable |

---

# 17. Tóm tắt Hypertable TimescaleDB

```text
prices                  -> chunk theo trade_date (1 tháng)
adjusted_prices         -> chunk theo trade_date (1 tháng)
index_prices            -> chunk theo trade_date (1 tháng)
foreign_flows           -> chunk theo trade_date (1 tháng)
prop_trading_flows      -> chunk theo trade_date (1 tháng)
valuation_daily         -> chunk theo trade_date (1 tháng)
macro_indicators        -> chunk theo period_date (1 năm)
features                -> chunk theo trade_date (1 tháng)
factor_scores           -> chunk theo trade_date (1 tháng)
signals                 -> chunk theo trade_date (1 tháng)
market_regimes          -> chunk theo trade_date (1 năm)
predictions             -> chunk theo trade_date (1 tháng)
portfolio_snapshots     -> chunk theo snapshot_date (1 tháng)
```

Chính sách retention/nén hoãn tới ADR sau khi biết khối lượng lưu trữ.

---

# 18. Chiến lược migration

- Công cụ: **Alembic** (SQLAlchemy) trong `database/migrations/`.
- Một migration một thay đổi logic; không bao giờ sửa migration đã merge.
- Dữ liệu seed (sàn, ngành, thành phần VN30) nằm trong `database/seeds/`.
- Chuyển hypertable TimescaleDB (`create_hypertable(...)`) chạy post-create ngay trong cùng migration tạo bảng gốc.

---

# 19. Mục mở cho vòng lặp tiếp

- Chốt chi tiết chính sách điều chỉnh cho truy vấn lưỡng thời `financial_statements` mà backtester dùng.
- Quyết object storage (tương thích S3) cho blob tài liệu thô mà `documents.storage_path` trỏ tới.
- Quyết chính sách nén/retention từng hypertable khi đo được khối lượng lịch sử EOD VN30.
