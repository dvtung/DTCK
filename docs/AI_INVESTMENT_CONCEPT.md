# AI-powered Investment Research & Decision Support Platform

- Quan sát thị trường
- Phát hiện cơ hội
- Phân tích doanh nghiệp
- Đánh giá rủi ro
- Đưa ra investment thesis có bằng chứng

## 1. Tầng 1 — Deterministic / Quantitative

Không dùng LLM:
```
Price
Volume
Financial Statements
Macro Data
Foreign Flow
Corporate Events
        ↓
Feature Engineering
        ↓
Quant Engine
        ↓
Scores / Signals / Features
```


Ví dụ:

```
RSI = 63.2
ROE = 21.5%
Revenue YoY = +18.2%
EPS YoY = +24.1%
Debt/Equity = 0.42
PE = 11.8
Industry PE = 16.3
Foreign Flow = +125B
Momentum 20D = +8.4%
```

Những thứ này không cần AI Agent.


## 2. Tầng 2 mới là AI Agent
Sau khi Quant Engine tạo ra dữ liệu có cấu trúc:
```json
{
  "symbol": "FPT",
  "technical_score": 82,
  "fundamental_score": 91,
  "valuation_score": 76,
  "momentum_score": 88,
  "risk_score": 73,
  "macro_score": 80
}
```
AI Agent mới bắt đầu làm việc.

Nó sẽ hỏi:

`"Tại sao FPT đang được score 84?"`

Sau đó gọi tools:

```
get_financials()
get_valuation()
get_technical()
get_news()
get_macro()
get_company_events()
get_peer_comparison()
```
và xây dựng:

```
Investment Thesis
+
Supporting Evidence
+
Contradicting Evidence
+
Risks
+
Catalysts
+
Confidence
```

Đây mới thực sự là Agentic AI.

## 3. Kiến trúc
Kiến trúc tôi muốn anh hướng tới:

                       ┌──────────────────────┐
                       │      DATA SOURCES    │
                       │                      │
                       │ Market               │
                       │ Financial            │
                       │ News                 │
                       │ Macro                │
                       │ Corporate Events     │
                       │ Foreign Flow         │
                       └──────────┬───────────┘
                                  │
                                  ▼
                       ┌──────────────────────┐
                       │    DATA INGESTION    │
                       │                      │
                       │ API / ETL / Streaming│
                       └──────────┬───────────┘
                                  │
                                  ▼
                 ┌────────────────────────────────┐
                 │          DATA PLATFORM          │
                 │                                │
                 │ Raw Data                       │
                 │ Clean Data                     │
                 │ Historical Data                │
                 │ Feature Store                  │
                 │ Document Store                 │
                 └───────────────┬────────────────┘
                                 │
             ┌───────────────────┼──────────────────┐
             │                   │                  │
             ▼                   ▼                  ▼
      ┌────────────┐      ┌────────────┐     ┌────────────┐
      │ QUANT      │      │ NLP / RAG   │     │ MARKET     │
      │ ENGINE     │      │ ENGINE     │     │ REGIME     │
      └─────┬──────┘      └─────┬──────┘     └─────┬──────┘
            │                   │                  │
            └───────────────────┼──────────────────┘
                                ▼
                     ┌─────────────────────┐
                     │  INVESTMENT ENGINE  │
                     │                     │
                     │ Multi-factor score  │
                     │ Ranking             │
                     │ Risk                │
                     │ Opportunity         │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │    AI AGENT LAYER   │
                     │                     │
                     │ Research Agent      │
                     │ Analysis Agent      │
                     │ Portfolio Agent     │
                     │ Monitoring Agent    │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │ ORCHESTRATOR / LLM  │
                     │                     │
                     │ Tool Calling        │
                     │ Evidence synthesis  │
                     │ Reasoning           │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │ RISK / GUARDRAIL    │
                     │                     │
                     │ Validation          │
                     │ Confidence          │
                     │ Compliance          │
                     │ Audit               │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │ DASHBOARD / CHAT    │
                     │ ALERT / REPORT      │
                     └─────────────────────┘

## 4. Tách `"Prediction"` và `"Reasoning"`
### 4.1. Prediction Engine
```
Input:
price
volume
fundamental
macro
sentiment
factor

        ↓

ML / Statistical Models

        ↓

P(return > threshold)
Expected return
Volatility
Drawdown
Risk
```

### 4.2. Reasoning Engine
LLM nhận:
```
Prediction
+
Features
+
Evidence
+
News
+
Financial data
```
rồi trả:

```
Why?
What supports it?
What contradicts it?
What could invalidate thesis?
What should investor monitor?
```
LLM không được tự tính toán những số liệu quan trọng.

## 5.`"Confidence Score"` trong tài liệu cần thiết kế lại
Tài liệu nói:

`confidence dựa trên độ đồng thuận giữa các agent.`

Tôi không khuyến nghị dùng cách này làm confidence chính.

Ví dụ:

```
Technical Agent       BUY
Fundamental Agent     BUY
Macro Agent           BUY
News Agent            BUY
```

không có nghĩa:

`Confidence = 100%`

Tôi đề xuất:

```
Confidence =
    Model calibration
  + Historical hit rate
  + Data quality
  + Signal agreement
  + Market regime compatibility
  + Evidence quality
  ```

Ví dụ:

```
Signal:       POSITIVE
Confidence:   74%

Model accuracy:
68%

Data quality:
93%

Agent agreement:
82%

Historical regime performance:
76%
```

Như vậy confidence mới có ý nghĩa thống kê.

## 6. Cần bổ sung `"Market Regime Engine"`
Đây là thành phần tôi cho rằng tài liệu đang thiếu.

Không nên phân tích một cổ phiếu độc lập với trạng thái thị trường.

Ví dụ:

```
Regime A:
Bull Market

Regime B:
Sideway

Regime C:
Bear Market

Regime D:
High Volatility
```

Một strategy có thể:
```
Bull:
Sharpe = 1.8

Sideway:
Sharpe = 0.9

Bear:
Sharpe = -0.7
```
Nếu hiện tại:
```
Regime = Bear
```
thì hệ thống phải giảm confidence.

Kiến trúc:
```
VNINDEX
Market Breadth
Volatility
Liquidity
Foreign Flow
Interest Rate
Sector Rotation
        ↓
Market Regime Classifier
        ↓
Bull / Sideway / Bear / Crisis
```
Đây sẽ là một component rất quan trọng.

## 7. Cần thêm `Portfolio Agent`
Tài liệu hiện tại chủ yếu tập trung vào stock selection.

Nhưng:

`Chọn cổ phiếu tốt ≠ xây portfolio tốt.`

Ví dụ hệ thống chọn:
```
FPT
VCB
MWG
HPG
SSI
```
có thể tất cả đều tốt.

Nhưng nếu `correlation` cao hoặc cùng chịu một `macro factor`, `portfolio` vẫn rủi ro.

Tôi đề xuất thêm:

**Portfolio Agent**

Nhiệm vụ:
```
Position sizing
Correlation
Sector exposure
Beta
Volatility
Maximum drawdown
Portfolio concentration
Risk budget
```
Ví dụ:
```
FPT      20%
VCB      20%
MWG      15%
HPG      10%
Cash     35%
```
Agent phải giải thích:

```
Tại sao 20%, không phải 10%?
```
## 8. Data Architecture cần nâng cấp
Đối với MVP, tôi không khuyên anh dựng quá nhiều database.

Anh có thể bắt đầu:
```
PostgreSQL
   ├── market data
   ├── financial data
   ├── features
   ├── signals
   ├── portfolio
   ├── news metadata
   └── audit logs

Qdrant
   └── news / reports / documents
```
Sau này mới thêm:
```
Object Storage
Data Lake
Kafka
ClickHouse
Elasticsearch
```
Đây phù hợp hơn với cách anh đang học và xây hệ thống từng bước.

## 9. RAG cũng cần thiết kế khác với RAG thông thường
Không nên đơn giản:
```
News
 ↓
Embedding
 ↓
Qdrant
 ↓
Top-K
 ↓
LLM
```
Tôi đề xuất:
```
Query
 ↓
Metadata filtering
 ↓
Vector search
 ↓
Keyword search
 ↓
Recency weighting
 ↓
Source reliability
 ↓
Reranking
 ↓
Evidence set
 ↓
LLM
```
Ví dụ user hỏi:

`"Tại sao FPT tăng mạnh hôm nay?"`

hệ thống cần ưu tiên:
```
News trong 24h
+
Corporate announcement
+
Trading volume
+
Foreign flow
+
Price movement
```
thay vì lấy một bài báo cách đây 6 tháng chỉ vì semantic similarity cao.

## 10. Cần xây "Evidence Layer"

Mọi nhận định phải có:
```
Claim
 ↓
Evidence
 ↓
Source
 ↓
Timestamp
 ↓
Data version
```
Ví dụ:
```
Claim:
Lợi nhuận FPT tăng mạnh.

Evidence:
Net profit YoY = +21.4%

Source:
Financial Statement Q2/2026

Timestamp:
2026-08-15
```
LLM chỉ được phép nói:

`"Lợi nhuận tăng 21.4% YoY"`

nếu Evidence Layer có dữ liệu đó. Điều này giảm hallucination rất mạnh.

## 11. Backtesting phải trở thành trung tâm hệ thống
**First-class component.**

Kiến trúc:
```
Strategy
   ↓
Historical Data
   ↓
Feature Generation
   ↓
Signal
   ↓
Portfolio Construction
   ↓
Execution Simulation
   ↓
Performance
```
Phải tính ít nhất:
```
CAGR
Annual Return
Volatility
Sharpe
Sortino
Max Drawdown
Calmar
Win Rate
Profit Factor
Turnover
Transaction Cost
```
Và quan trọng:

**Không được có look-ahead bias.**

Ví dụ:
```
BCTC Q2
```
không được sử dụng cho giao dịch:
```
trước ngày BCTC thực sự được công bố.
```
Đây là một trong những lỗi nguy hiểm nhất của hệ thống quantitative.

## 12. Thêm "Prediction Registry"

Mỗi prediction phải được lưu.

Ví dụ:
```
Prediction ID: 202609060001

Symbol: FPT

Time:
2026-09-06 15:00

Prediction:
Positive

Expected return:
+5.8%

Horizon:
20 trading days

Confidence:
72%

Model:
XGBoost v1.4

Feature version:
feature_2026_09_06_v3
```
20 ngày sau:
```
Actual return:
+7.1%

Prediction:
Correct
```
Sau 1.000 prediction:
```
Calibration
Accuracy
Precision
Recall
Expected vs Actual
```
Hệ thống bắt đầu học được hệ thống của chính nó hoạt động tốt ở đâu và kém ở đâu.

## 13. Tech stack
**MVP**

Tôi chọn:
```
Python
FastAPI
PostgreSQL
TimescaleDB
Qdrant
Pandas
Polars
NumPy
scikit-learn
XGBoost / LightGBM
Pydantic
LangGraph
Streamlit
Docker
Git
```
LLM:
```
Claude / OpenAI
```
nhưng LLM provider phải được abstraction.

Ví dụ:
```
LLMProvider
   ├── OpenAIProvider
   ├── ClaudeProvider
   └── LocalProvider
```
Không hard-code application vào một model.

## 14. Không cần Kafka/Airflow ngay
Production lớn: đúng.

**MVP**: quá sớm.

Ban đầu:
```
cron
+
Python worker
+
FastAPI
```
là đủ.

Sau này:
```
Scheduler
      ↓
Task Queue
      ↓
Workers
```
và khi volume thực sự lớn:
```
Kafka
```
Không nên xây infrastructure trước khi có workload cần nó.

## 15. Roadmap
**Phase 0 — Foundation**
```
Git
Docker
Python
PostgreSQL
FastAPI
Project architecture
```
**Phase 1 — Market Data**
```
Price
Volume
Index
Corporate actions
Historical database
```
**Phase 2 — Quant Engine**
```
Indicators
Factors
Fundamental ratios
Scoring
Ranking
```
**Phase 3 — Backtesting**
```
Strategy
Portfolio
Transaction cost
Walk-forward
Metrics
```
**Phase 4 — RAG**
```
News
Financial reports
Corporate events
Embedding
Qdrant
Hybrid retrieval
Reranking
```
**Phase 5 — AI Agent**
```
Tool calling
Research Agent
Analysis Agent
Monitoring Agent
Orchestrator
```
**Phase 6 — ML Prediction**
```
Feature dataset
XGBoost/LightGBM
Probability
Calibration
Regime
```
**Phase 7 — Portfolio Intelligence**
```
Position sizing
Risk
Correlation
Portfolio optimization
Alerts
```

## 16. MVP đầu tiên
**"Vietnam Stock Intelligence Engine"**
Input:
```
VN30
```
Output:
```
┌────────────────────────────────────┐
│ STOCK RANKING                      │
├──────┬──────┬──────┬──────┬────────┤
│Code  │Score │Fund. │Tech. │Risk    │
├──────┼──────┼──────┼──────┼────────┤
│FPT   │86    │92    │84    │Low     │
│VCB   │83    │90    │77    │Low     │
│MWG   │79    │78    │86    │Medium  │
│HPG   │72    │71    │76    │High    │
└──────┴──────┴──────┴──────┴────────┘
```
Sau đó click FPT:
```
FPT
─────────────────────────

Fundamental     92
Technical       84
Valuation       76
Momentum        88
Risk            73

Overall         86

Market Regime:
Bullish

Investment Thesis:
...

Catalysts:
...

Risks:
...

Evidence:
...
```
Nếu chúng ta xây được sản phẩm này, phần Agent phía sau sẽ trở nên rất rõ ràng.

## 17. Cách Agent hoạt động
User hỏi:
```
"Phân tích FPT"
```
Orchestrator không tự trả lời.

Nó lập kế hoạch:
```
PLAN

1. Get current market data
2. Get fundamental data
3. Get valuation
4. Get technical indicators
5. Get latest news
6. Get corporate events
7. Get market regime
8. Get peer comparison
9. Calculate risk
10. Generate investment thesis
```
Sau đó:
```
Tool Call
   ↓
Structured Data
   ↓
Evidence
   ↓
LLM
```
Ví dụ:
```python
get_stock_price("FPT")
get_fundamentals("FPT")
get_valuation("FPT")
get_technical("FPT")
get_news("FPT", days=30)
get_market_regime()
get_peer_analysis("FPT")
```
LLM không trực tiếp truy cập database.

LLM chỉ sử dụng tools.

Đây là điểm rất quan trọng trong Agent architecture.

## 18. Output chuẩn của Agent
Dùng Pydantic:
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
Như vậy:
```
LLM
 ↓
Structured Output
 ↓
Validation
 ↓
Database
 ↓
Dashboard
```
thay vì:
```
LLM
 ↓
một đoạn văn
```

## 19. "Investment Thesis" và "Recommendation" phải tách
Ví dụ:
```
Investment Thesis:

FPT có chất lượng cơ bản tốt,
tăng trưởng lợi nhuận tích cực,
momentum cải thiện...
```
không đồng nghĩa:
```
BUY
```
Hệ thống có thể nói:
```
Thesis: Positive

Valuation: Fair

Risk: Medium

Expected return:
+7%

Confidence:
71%
```
Sau đó người dùng tự quyết định.

## 20. Về pháp lý

Nếu hệ thống chỉ dùng cá nhân:
```
Research assistant
```
thì bài toán khác rất nhiều so với:

dịch vụ cung cấp khuyến nghị đầu tư cho khách hàng.

Tôi đề xuất ngay từ đầu architecture phải có:
```
Decision Support
```
thay vì hard-code:
```
BUY / SELL
```
và lưu:
```
Data
Model
Prediction
Evidence
Timestamp
Decision
```
để audit được.

## 21. Những phần tôi đánh giá tài liệu hiện tại làm tốt

Có 5 điểm rất tốt:

**1. Không kỳ vọng LLM dự đoán thị trường**

Đây là tư duy đúng. Tài liệu xác định mục tiêu là tổng hợp thông tin, phát hiện tín hiệu và hỗ trợ quyết định.

**2. Có backtesting**

Đây là bắt buộc.

**3. Có Human-in-the-loop**

Rất cần thiết trong financial AI.

**4. Có audit log**

Đặc biệt quan trọng khi hệ thống bắt đầu đưa ra các nhận định định kỳ.

**5. Đã phân biệt ML và LLM**

Phần đề xuất XGBoost/LightGBM cho forecasting và LLM làm diễn giải là hướng tôi đồng ý.

## 22. Những phần tôi muốn sửa
| Hiện tại | Tôi đề xuất |
| :--- | :--- |
| Multi-Agent sớm	| Quant Engine trước | 
| Confidence = agent agreement	| Statistical calibration| 
| Forecasting/Reasoning gộp	| Prediction ≠ Reasoning| 
| RAG đơn giản	| Hybrid retrieval + reranking| 
| Kafka sớm	| Cron/worker trước| 
| Airflow sớm	| Scheduler đơn giản| 
| Stock selection	| Stock + Portfolio| 
| Dashboard sau	| Evaluation trước| 
| LLM là trung tâm	| Data/Quant là trung tâm| 
| Recommendation	| Evidence-based thesis| 
| Backtest là một phase	| Backtest là nền tảng xuyên suốt| 

## 23. Định hướng cuối cùng 

Tôi muốn chúng ta xây hệ thống theo mô hình:

             ┌─────────────────┐
             │    MARKET       │
             │    DATA         │
             └────────┬────────┘
                      ↓
             ┌─────────────────┐
             │ DATA PLATFORM   │
             └────────┬────────┘
                      ↓
             ┌─────────────────┐
             │ QUANT ENGINE    │
             │                 │
             │ Factors         │
             │ Indicators      │
             │ Valuation       │
             │ Risk            │
             └────────┬────────┘
                      ↓
             ┌─────────────────┐
             │ BACKTEST ENGINE │
             └────────┬────────┘
                      ↓
             ┌─────────────────┐
             │ ML PREDICTION   │
             └────────┬────────┘
                      ↓
             ┌─────────────────┐
             │ AI AGENT        │
             │                 │
             │ Research        │
             │ Analysis        │
             │ Monitoring      │
             └────────┬────────┘
                      ↓
             ┌─────────────────┐
             │ LLM             │
             │ Reasoning/RAG   │
             └────────┬────────┘
                      ↓
             ┌─────────────────┐
             │ RISK / AUDIT    │
             └────────┬────────┘
                      ↓
             ┌─────────────────┐
             │ HUMAN           │
             │ DECISION        │
             └─────────────────┘
## 24. Và đề xuất xây theo từng bước

Với nền tảng kỹ thuật anh đang có về Python, FastAPI, Docker, Qdrant, vector search, AI Agent, tôi không nghĩ nên bắt đầu bằng việc học thêm quá nhiều framework. Ta nên xây thật một hệ thống, vừa xây vừa học.

Tôi đề xuất thứ tự thực hiện:

**STEP 1 — System Specification**

Chốt:
```
Market:
Vietnam

Exchange:
HOSE + HNX + UPCOM

Initial universe:
VN30 → mở rộng toàn thị trường

Frequency:
EOD trước → intraday sau

Investment horizon:
Short / Medium / Long

Output:
Score + Thesis + Risk + Evidence
```
**STEP 2 — Data Model**

Thiết kế PostgreSQL:
```
stocks
prices
volumes
financial_statements
financial_ratios
corporate_events
news
macro_data
features
signals
predictions
backtests
portfolio
agent_runs
evidence
```
**STEP 3 — Data Pipeline**
```
Source
 ↓
Collector
 ↓
Validator
 ↓
Normalizer
 ↓
PostgreSQL
```
**STEP 4 — Quant Engine**

Xây:
```
Technical indicators
Fundamental factors
Valuation
Momentum
Quality
Risk
```
**STEP 5 — Scoring Engine**
```
Fundamental 30%
Technical   20%
Momentum    15%
Valuation   15%
Quality     10%
Risk        10%
```
Nhưng đây chỉ là baseline. Sau đó dùng backtest để kiểm chứng và học trọng số.

**STEP 6 — Backtesting**

Không có bước này thì không cho phép hệ thống tự tin đưa ra signal.

**STEP 7 — Qdrant + RAG**

Tích hợp kinh nghiệm vector search mà anh đã làm:
```
News
Reports
Corporate events
Research reports
        ↓
Embedding
        ↓
Qdrant
        ↓
Hybrid Retrieval
        ↓
Reranker
```
**STEP 8 — Agent**

Lúc này mới xây:
```
Research Agent
Analysis Agent
Monitoring Agent
Portfolio Agent
Orchestrator
```
**STEP 9 — ML Prediction**
```
Feature Store
 ↓
XGBoost / LightGBM
 ↓
Probability
 ↓
Calibration
```
**STEP 10 — Production**

Cuối cùng:
```
FastAPI
Docker
PostgreSQL
Qdrant
Worker
Monitoring
Dashboard
Authentication
Audit
Alert
```