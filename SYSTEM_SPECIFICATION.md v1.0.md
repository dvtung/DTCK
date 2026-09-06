# SYSTEM SPECIFICATION

## AI INVESTMENT RESEARCH & DECISION INTELLIGENCE PLATFORM

**Version:** 1.0  
**Status:** Draft / Architecture Baseline  
**Date:** 2026-09-06  
**Market:** Vietnam Stock Market  
**Primary Market:** HOSE / HNX / UPCOM  
**System Type:** AI-powered Investment Research & Decision Support Platform

---

# 1. Document Purpose

Tài liệu này định nghĩa đặc tả hệ thống cấp cao cho nền tảng:

> **AI Investment Research & Decision Intelligence Platform**

Hệ thống có nhiệm vụ thu thập, chuẩn hóa, phân tích và tổng hợp dữ liệu thị trường chứng khoán Việt Nam; sử dụng Quantitative Finance, Machine Learning, RAG và Agentic AI để hỗ trợ người dùng nghiên cứu và ra quyết định đầu tư.

Hệ thống **không được thiết kế như một hệ thống tự động quyết định đầu tư thay con người**.

Mục tiêu:

```text
DATA
  ↓
QUANTITATIVE ANALYSIS
  ↓
MACHINE LEARNING
  ↓
AI AGENT
  ↓
EVIDENCE-BASED REASONING
  ↓
RISK ANALYSIS
  ↓
HUMAN DECISION
```

---

# 2. System Objectives

## 2.1. Primary Objectives

Hệ thống phải có khả năng:

1. Thu thập dữ liệu thị trường.
2. Lưu trữ dữ liệu lịch sử.
3. Chuẩn hóa dữ liệu từ nhiều nguồn.
4. Tính toán các quantitative factors.
5. Phân tích technical indicators.
6. Phân tích fundamental indicators.
7. Phân tích valuation.
8. Phân tích momentum.
9. Phân tích risk.
10. Xác định market regime.
11. Screening và ranking cổ phiếu.
12. Backtesting chiến lược.
13. Dự báo xác suất/xu hướng bằng ML.
14. Thu thập và phân tích tin tức.
15. Xây dựng RAG knowledge base.
16. Sử dụng AI Agent để điều phối quá trình nghiên cứu.
17. Sinh investment thesis có evidence.
18. Theo dõi prediction sau khi được tạo.
19. Đánh giá hiệu quả của model/strategy.
20. Cung cấp dashboard, report và alert.

---

# 3. Non-Objectives

Hệ thống phiên bản 1.0 không nhằm:

- Đảm bảo lợi nhuận.
- Dự đoán chính xác tuyệt đối giá cổ phiếu.
- Thay thế chuyên gia đầu tư.
- Tự động thực hiện giao dịch chứng khoán.
- Cung cấp tư vấn đầu tư thương mại cho bên thứ ba khi chưa đánh giá đầy đủ yêu cầu pháp lý.
- Cho phép LLM tự tạo số liệu tài chính.
- Cho phép LLM tự quyết định BUY/SELL mà không có quantitative evidence.

---

# 4. Core Design Principles

## 4.1. Data First

Dữ liệu là nền tảng của toàn bộ hệ thống.

```text
Bad Data
   ↓
Bad Features
   ↓
Bad Model
   ↓
Bad Agent
```

Do đó data quality phải được kiểm soát trước khi dữ liệu được sử dụng.

---

## 4.2. Deterministic Calculation First

Các phép tính tài chính và quantitative phải được thực hiện bởi software engine.

Ví dụ:

- RSI
- MACD
- MA
- EMA
- P/E
- P/B
- ROE
- ROA
- EPS
- Revenue Growth
- Profit Growth
- Debt/Equity
- Volatility
- Sharpe Ratio
- Maximum Drawdown

Không giao các phép tính quan trọng này cho LLM.

---

## 4.3. LLM Is a Reasoning Layer

LLM chủ yếu thực hiện:

- Planning
- Tool selection
- Information synthesis
- Natural language reasoning
- Evidence interpretation
- Report generation

LLM không phải là source of truth.

---

## 4.4. Evidence-Based Reasoning

Mọi nhận định quan trọng phải truy xuất được:

```text
Claim
 ↓
Evidence
 ↓
Source
 ↓
Timestamp
 ↓
Data Version
```

---

## 4.5. Backtest Before Deployment

Một strategy/model không được coi là production-ready nếu chưa được kiểm thử trên dữ liệu lịch sử phù hợp.

Phải kiểm soát:

- Look-ahead bias
- Survivorship bias
- Data leakage
- Overfitting
- Transaction cost
- Slippage
- Corporate actions

---

## 4.6. Human-in-the-loop

Hệ thống hỗ trợ con người.

```text
AI Analysis
     ↓
Risk Validation
     ↓
Human Review
     ↓
Investment Decision
```

---

## 4.7. Full Auditability

Hệ thống phải lưu được:

- Input data
- Feature version
- Model version
- Prompt version
- Agent execution
- Tool calls
- Evidence
- Prediction
- Output
- Timestamp

---

# 5. Target Market

## 5.1. Initial Scope

Thị trường:

```text
Vietnam
```

Sàn:

```text
HOSE
HNX
UPCOM
```

## 5.2. Initial Universe

MVP:

```text
VN30
```

Sau khi hệ thống ổn định:

```text
VN100
        ↓
HOSE
HNX
UPCOM
        ↓
Full Market
```

---

# 6. Investment Horizons

Hệ thống hỗ trợ ba horizon:

### Short Term

```text
1 - 20 trading days
```

### Medium Term

```text
1 - 6 months
```

### Long Term

```text
6 - 36 months
```

Mỗi model/strategy phải khai báo rõ horizon.

Không được sử dụng một prediction mà không xác định thời gian dự báo.

---

# 7. System Architecture

## 7.1. Logical Architecture

```text
┌───────────────────────────────────────────────┐
│                 DATA SOURCES                 │
│                                               │
│ Market │ Financial │ News │ Macro │ Events   │
└───────────────────────┬───────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│              DATA INGESTION                   │
│                                               │
│ API / ETL / Collector / Scheduler             │
└───────────────────────┬───────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│                DATA PLATFORM                  │
│                                               │
│ Raw │ Clean │ Curated │ Feature │ Documents   │
└──────────────┬───────────────────────┬────────┘
               │                       │
               ▼                       ▼
       ┌───────────────┐       ┌──────────────┐
       │ QUANT ENGINE  │       │ RAG ENGINE   │
       └───────┬───────┘       └──────┬───────┘
               │                       │
               ▼                       ▼
       ┌───────────────┐       ┌──────────────┐
       │ ML ENGINE     │       │ EVIDENCE     │
       │               │       │ ENGINE       │
       └───────┬───────┘       └──────┬───────┘
               │                       │
               └───────────┬───────────┘
                           ▼
                 ┌───────────────────┐
                 │ INVESTMENT ENGINE │
                 └─────────┬─────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │   AI AGENT LAYER  │
                 │                   │
                 │ Research Agent    │
                 │ Analysis Agent    │
                 │ Monitoring Agent  │
                 │ Portfolio Agent   │
                 └─────────┬─────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │ LLM ORCHESTRATOR  │
                 └─────────┬─────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │ RISK / GUARDRAIL  │
                 └─────────┬─────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │ HUMAN / DASHBOARD │
                 └───────────────────┘
```

---

# 8. Major System Components

## 8.1. Data Ingestion Layer

Responsibilities:

- Data collection
- Scheduling
- API integration
- Data validation
- Source tracking
- Retry
- Error handling

Initial implementation:

```text
Python
FastAPI
Scheduler
Workers
```

Future:

```text
Kafka
Airflow / Dagster
Distributed Workers
```

---

# 9. Data Platform

## 9.1. Primary Database

Initial database:

```text
PostgreSQL
```

Time-series extension:

```text
TimescaleDB
```

Responsibilities:

- Market data
- Financial statements
- Fundamental ratios
- Technical features
- Signals
- Predictions
- Portfolio
- Agent runs
- Audit logs

---

## 9.2. Vector Database

Initial choice:

```text
Qdrant
```

Use cases:

- News
- Annual reports
- Quarterly reports
- Corporate disclosures
- Research documents
- Company information

---

## 9.3. Object Storage

Future component:

```text
S3-compatible Object Storage
```

Use for:

- Original documents
- PDF reports
- Raw datasets
- Data snapshots
- Backtest artifacts

---

# 10. Data Domains

The system must organize data into the following domains.

## 10.1. Market Data

- OHLC
- Adjusted OHLC
- Volume
- Trading value
- Market capitalization
- Foreign net flow
- Proprietary trading flow
- Index data

---

## 10.2. Fundamental Data

- Revenue
- Gross profit
- Operating profit
- Net profit
- EPS
- Assets
- Liabilities
- Equity
- Operating cash flow
- Free cash flow
- Debt
- Interest expense

---

## 10.3. Valuation Data

- P/E
- Forward P/E
- P/B
- EV/EBITDA
- EV/Sales
- Dividend Yield
- PEG

---

## 10.4. Technical Data

- SMA
- EMA
- RSI
- MACD
- Bollinger Bands
- ATR
- ADX
- Volume indicators
- Momentum
- Relative strength

---

## 10.5. Macro Data

- GDP
- CPI
- Interest rates
- Exchange rates
- Credit growth
- Money supply
- Commodity prices
- Economic indicators

---

## 10.6. Corporate Events

- Earnings release
- Dividend
- Stock split
- Rights issue
- AGM
- Management changes
- M&A
- Legal events
- Major investment
- Capital increase

---

## 10.7. News

Every news item should contain:

```text
source
title
content
published_at
symbol
sector
event_type
sentiment
importance
embedding
```

---

# 11. Quantitative Engine

The Quant Engine is one of the most important components.

It must operate independently from LLM.

## 11.1. Technical Factor

Example:

```text
Trend
Momentum
Relative Strength
Volume
Volatility
```

Output:

```text
technical_score: 0-100
```

---

## 11.2. Fundamental Factor

Example:

```text
Revenue Growth
EPS Growth
ROE
ROA
Margin
Debt
Cash Flow
Quality
```

Output:

```text
fundamental_score: 0-100
```

---

## 11.3. Valuation Factor

Compare:

```text
Company
vs
Industry
vs
Historical valuation
```

Output:

```text
valuation_score: 0-100
```

---

## 11.4. Momentum Factor

Measure:

- 5D return
- 20D return
- 60D return
- 120D return
- Relative strength
- Volume expansion

---

## 11.5. Risk Factor

Measure:

- Volatility
- Beta
- Maximum drawdown
- Liquidity
- Gap risk
- Earnings risk
- Debt risk

---

# 12. Multi-Factor Scoring

Initial baseline:

```text
Fundamental      30%
Technical        20%
Momentum         15%
Valuation        15%
Quality          10%
Risk             10%
```

Formula:

```text
Overall Score =
    Fundamental × 0.30
  + Technical   × 0.20
  + Momentum    × 0.15
  + Valuation   × 0.15
  + Quality     × 0.10
  + Risk        × 0.10
```

Important:

> Các trọng số trên chỉ là baseline ban đầu và phải được kiểm chứng bằng backtesting.

Không được giả định rằng chúng tối ưu.

---

# 13. Market Regime Engine

Hệ thống phải xác định trạng thái thị trường.

Initial regimes:

```text
BULL
SIDEWAYS
BEAR
HIGH_VOLATILITY
CRISIS
```

Input:

- VNINDEX trend
- Market breadth
- Volume
- Volatility
- Foreign flow
- Interest rate
- Liquidity
- Sector rotation

Output:

```json
{
  "regime": "BULL",
  "confidence": 0.78
}
```

Market regime phải được sử dụng như một contextual feature cho:

- Stock ranking
- ML prediction
- Portfolio construction
- Risk assessment

---

# 14. Machine Learning Engine

LLM không phải prediction engine chính.

Initial ML:

```text
XGBoost
LightGBM
Scikit-learn
```

Potential targets:

```text
P(return > 0)
P(return > 5%)
P(return > 10%)
Expected return
Volatility
Drawdown
```

Ví dụ:

```text
P(+5% in 20D) = 0.67
```

Model phải có:

- Training dataset version
- Feature version
- Model version
- Training timestamp
- Validation metrics

---

# 15. Model Evaluation

Metrics:

```text
Accuracy
Precision
Recall
F1
ROC-AUC
Log Loss
Brier Score
Calibration
```

Investment metrics:

```text
CAGR
Sharpe
Sortino
Calmar
Maximum Drawdown
Win Rate
Profit Factor
Turnover
Transaction Cost
```

Không đánh giá model chỉ bằng prediction accuracy.

---

# 16. Backtesting Engine

Backtesting là core infrastructure.

Pipeline:

```text
Historical Data
      ↓
Feature Generation
      ↓
Signal Generation
      ↓
Portfolio Construction
      ↓
Execution Simulation
      ↓
Transaction Cost
      ↓
Performance
```

Phải hỗ trợ:

- In-sample
- Out-of-sample
- Walk-forward
- Rolling window
- Parameter sensitivity

---

# 17. Bias Prevention

Hệ thống phải phát hiện/ngăn:

### Look-ahead Bias

Không được sử dụng dữ liệu chưa tồn tại tại thời điểm prediction.

### Survivorship Bias

Universe lịch sử phải phản ánh cổ phiếu thực sự tồn tại tại từng thời điểm.

### Data Leakage

Không để dữ liệu tương lai lọt vào training feature.

### Overfitting

Phải kiểm tra:

```text
Train
Validation
Test
Out-of-sample
Walk-forward
```

---

# 18. RAG Engine

## 18.1. Documents

RAG knowledge base gồm:

```text
News
Financial Reports
Corporate Disclosures
Annual Reports
Quarterly Reports
Research Reports
Company Information
```

## 18.2. Retrieval Pipeline

```text
User Query
    ↓
Metadata Filter
    ↓
Vector Search
    ↓
Keyword Search
    ↓
Recency Weight
    ↓
Source Reliability
    ↓
Reranking
    ↓
Evidence Set
```

---

# 19. Evidence Engine

Evidence object:

```json
{
  "claim": "...",
  "source": "...",
  "source_type": "financial_report",
  "published_at": "...",
  "data_timestamp": "...",
  "evidence": "...",
  "confidence": 0.91
}
```

Evidence phải được liên kết với:

- Analysis
- Prediction
- Agent run
- Report

---

# 20. Agent Architecture

## 20.1. Research Agent

Nhiệm vụ:

- Tìm kiếm thông tin
- Tổng hợp company profile
- Thu thập evidence
- Phát hiện sự kiện quan trọng

---

## 20.2. Analysis Agent

Nhiệm vụ:

- Phân tích một mã cổ phiếu
- Gọi Quant Tools
- Gọi RAG Tools
- Tổng hợp evidence
- Xây dựng investment thesis

---

## 20.3. Monitoring Agent

Theo dõi:

- Price
- Volume
- News
- Corporate events
- Fundamental changes
- Risk signals

Có thể phát alert khi:

```text
Signal changed
Risk increased
Important news
Technical breakout
Fundamental deterioration
```

---

## 20.4. Portfolio Agent

Nhiệm vụ:

- Position sizing
- Correlation
- Sector exposure
- Portfolio risk
- Concentration
- Drawdown
- Risk budget

---

# 21. Orchestrator

Orchestrator là trung tâm điều phối Agent.

Ví dụ:

```text
User:
"Phân tích FPT"
```

Orchestrator tạo plan:

```text
1. Market regime
2. Price
3. Technical
4. Fundamental
5. Valuation
6. Peer comparison
7. News
8. Corporate events
9. Risk
10. ML prediction
11. Investment thesis
```

Sau đó thực hiện tool calls.

---

# 22. Tool Architecture

LLM không truy cập database trực tiếp.

LLM chỉ sử dụng tools.

Ví dụ:

```python
get_stock_price()
get_technical()
get_fundamentals()
get_valuation()
get_peer_analysis()
get_market_regime()
get_news()
get_corporate_events()
get_prediction()
get_risk()
```

Architecture:

```text
LLM
 ↓
Tool Call
 ↓
Application Service
 ↓
Database / Quant Engine / RAG
 ↓
Structured Result
 ↓
LLM
```

---

# 23. Structured Agent Output

Tất cả Agent output phải có schema.

Ví dụ:

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

# 24. Confidence Model

Confidence không chỉ dựa trên agreement giữa các Agent.

Confidence phải xem xét:

```text
Model calibration
Data quality
Signal agreement
Market regime
Historical performance
Evidence quality
```

Ví dụ:

```text
Confidence =
    Model Reliability
    × Data Quality
    × Regime Compatibility
    × Evidence Quality
```

Công thức chính thức sẽ được xác định sau khi có historical dataset.

---

# 25. Investment Thesis

Mỗi analysis phải có cấu trúc:

```text
Investment Thesis

1. Summary

2. Fundamental Strength

3. Technical Condition

4. Valuation

5. Momentum

6. Macro Environment

7. Catalysts

8. Risks

9. Contradicting Evidence

10. Invalidation Conditions

11. ML Prediction

12. Confidence

13. Evidence
```

---

# 26. Prediction Registry

Mỗi prediction phải được lưu.

Example:

```json
{
  "prediction_id": "...",
  "symbol": "FPT",
  "created_at": "...",
  "horizon": "20D",
  "expected_return": 0.058,
  "probability_positive": 0.67,
  "confidence": 0.72,
  "model_version": "xgb_1.0",
  "feature_version": "feature_1.0"
}
```

Sau khi horizon kết thúc:

```text
Prediction
     ↓
Actual Result
     ↓
Evaluation
     ↓
Model Performance
```

---

# 27. Portfolio Intelligence

Portfolio Agent phải đánh giá:

```text
Expected Return
Risk
Volatility
Correlation
Beta
Sector Exposure
Concentration
Liquidity
Maximum Drawdown
```

Portfolio decision phải được tách khỏi stock ranking.

---

# 28. API Layer

Primary backend:

```text
FastAPI
```

Initial API groups:

```text
/api/v1/market
/api/v1/stocks
/api/v1/fundamentals
/api/v1/technical
/api/v1/valuation
/api/v1/news
/api/v1/analysis
/api/v1/predictions
/api/v1/portfolio
/api/v1/backtests
/api/v1/agents
```

---

# 29. Dashboard

MVP:

```text
Streamlit
```

Production:

```text
React / Next.js
        +
FastAPI
```

Dashboard modules:

```text
Market Overview
Market Regime
Stock Screener
Stock Detail
Ranking
Signals
News
AI Analysis
Portfolio
Predictions
Backtest
Alerts
System Health
```

---

# 30. Alert System

Alert types:

```text
Technical Alert
Fundamental Alert
News Alert
Corporate Event
Risk Alert
Prediction Alert
Portfolio Alert
Market Regime Change
```

---

# 31. Audit System

Mỗi Agent execution phải lưu:

```text
agent_run_id
user_request
agent
model
model_version
prompt_version
tools_called
tool_inputs
tool_outputs
evidence
final_output
timestamp
latency
token_usage
```

Mục tiêu:

```text
Reproducibility
Debugging
Evaluation
Compliance
Model Improvement
```

---

# 32. Security

Initial requirements:

- API authentication
- Secret management
- Role-based access
- Database credentials isolation
- API key protection
- Audit logging

Không lưu:

- API key trong source code
- Password trong Git
- Secrets trong Docker image

---

# 33. Deployment Architecture

## MVP

```text
Docker Compose

┌──────────────────────────┐
│ FastAPI                  │
├──────────────────────────┤
│ Worker                   │
├──────────────────────────┤
│ PostgreSQL               │
├──────────────────────────┤
│ Qdrant                   │
├──────────────────────────┤
│ Streamlit                │
└──────────────────────────┘
```

## Production

Có thể mở rộng:

```text
Load Balancer
      ↓
FastAPI
      ↓
Task Queue
      ↓
Workers
      ↓
PostgreSQL / TimescaleDB
      ↓
Qdrant
      ↓
Object Storage
```

---

# 34. Initial Technology Stack

| Layer | Technology |
|---|---|
| Language | Python |
| Backend | FastAPI |
| Database | PostgreSQL |
| Time-series | TimescaleDB |
| Vector DB | Qdrant |
| Data Processing | Pandas / Polars |
| Numerical | NumPy |
| ML | Scikit-learn |
| ML Boosting | XGBoost / LightGBM |
| Agent Framework | LangGraph |
| LLM | Provider abstraction |
| Backtesting | VectorBT / custom engine |
| Dashboard MVP | Streamlit |
| Container | Docker |
| API | REST |
| Scheduler | Python scheduler / cron |
| Future Streaming | Kafka |
| Future Orchestration | Airflow / Dagster |

---

# 35. Repository Structure

Repository phải được tổ chức theo domain:

```text
ai-investment-platform/
│
├── apps/
│   ├── api/
│   ├── dashboard/
│   └── worker/
│
├── src/
│   ├── data/
│   │   ├── collectors/
│   │   ├── validators/
│   │   ├── normalizers/
│   │   └── pipelines/
│   │
│   ├── market/
│   │   ├── technical/
│   │   ├── fundamental/
│   │   ├── valuation/
│   │   ├── momentum/
│   │   └── risk/
│   │
│   ├── quant/
│   │   ├── factors/
│   │   ├── scoring/
│   │   └── signals/
│   │
│   ├── ml/
│   │   ├── datasets/
│   │   ├── training/
│   │   ├── models/
│   │   └── evaluation/
│   │
│   ├── rag/
│   │   ├── ingestion/
│   │   ├── embedding/
│   │   ├── retrieval/
│   │   └── reranking/
│   │
│   ├── agents/
│   │   ├── research/
│   │   ├── analysis/
│   │   ├── monitoring/
│   │   ├── portfolio/
│   │   └── orchestrator/
│   │
│   ├── evidence/
│   ├── portfolio/
│   ├── backtesting/
│   └── common/
│
├── database/
│   ├── migrations/
│   └── seeds/
│
├── tests/
│
├── notebooks/
│
├── configs/
│
├── scripts/
│
├── docs/
│
├── memory-bank/
│
├── offline_package/
│
├── docker/
│
├── docker-compose.yml
│
├── .env.example
├── pyproject.toml
└── README.md
```

---

# 36. Documentation Requirements

Project phải có thư mục:

```text
docs/
```

Tối thiểu:

```text
docs/
├── SYSTEM_SPECIFICATION.md
├── ARCHITECTURE.md
├── DATA_ARCHITECTURE.md
├── DATABASE_SCHEMA.md
├── QUANT_ENGINE.md
├── BACKTESTING.md
├── ML_ARCHITECTURE.md
├── RAG_ARCHITECTURE.md
├── AGENT_ARCHITECTURE.md
├── API_SPECIFICATION.md
├── DEPLOYMENT.md
└── SECURITY.md
```

Mỗi module/class/method quan trọng phải có documentation.

---

# 37. Memory Bank

Mọi task phát triển lớn phải cập nhật:

```text
memory-bank/
├── project-context.md
├── current-state.md
├── decisions.md
├── architecture-decisions.md
├── known-issues.md
├── tasks.md
└── changelog.md
```

Mục tiêu:

```text
Task N
 ↓
Implementation
 ↓
State
 ↓
Decision
 ↓
Next Task
```

Không mất context giữa các phiên phát triển.

---

# 38. Testing Strategy

Testing levels:

```text
Unit Test
Integration Test
Data Quality Test
Backtest Test
Agent Test
RAG Evaluation
API Test
End-to-End Test
```

Đặc biệt:

```text
Quant Calculation
```

phải có test với expected values.

Agent evaluation phải kiểm tra:

- Correct tool selection
- Correct data usage
- Evidence citation
- Hallucination
- Structured output
- Reasoning consistency

---

# 39. Data Quality Framework

Mỗi dataset phải có:

```text
Completeness
Accuracy
Consistency
Freshness
Uniqueness
Validity
```

Data Quality Score:

```text
0 - 100
```

Nếu dưới threshold:

```text
Do not use for prediction
```

---

# 40. Model Governance

Mỗi model phải có:

```text
Model ID
Version
Training Data
Feature Version
Training Period
Validation Period
Test Period
Metrics
Parameters
Owner
Created At
Status
```

Status:

```text
EXPERIMENTAL
VALIDATING
APPROVED
PRODUCTION
DEPRECATED
```

---

# 41. Agent Governance

Mỗi Agent phải có:

```text
Agent ID
Version
System Prompt Version
Available Tools
Allowed Data
Output Schema
Evaluation Score
Status
```

Agent không được tự ý:

- Thay đổi database schema.
- Thay đổi model.
- Thay đổi scoring weights.
- Thực hiện giao dịch.
- Xóa audit logs.

---

# 42. Risk Guardrails

System phải phát hiện:

```text
Low Data Quality
Model Drift
Extreme Volatility
Low Liquidity
Conflicting Signals
Insufficient Evidence
Stale Data
Unexpected Model Output
```

Khi xảy ra:

```text
Normal Analysis
        ↓
Warning
        ↓
Reduced Confidence
```

hoặc:

```text
Critical Risk
        ↓
Block Recommendation
```

---

# 43. Explainability

Mọi score phải có decomposition.

Ví dụ:

```text
FPT Overall Score: 86

Fundamental: 92
Technical:   84
Momentum:    88
Valuation:   76
Quality:     91
Risk:        73
```

Người dùng phải có thể drill-down:

```text
Fundamental 92
      ↓
Revenue Growth
EPS Growth
ROE
Margin
FCF
Debt
```

---

# 44. Decision Output

Không sử dụng output đơn giản:

```text
BUY
```

MVP output:

```text
Signal:
POSITIVE

Score:
86 / 100

Confidence:
72%

Expected Return:
+5.8%

Risk:
MEDIUM

Horizon:
20 trading days
```

Kèm:

```text
Thesis
Catalysts
Risks
Invalidation Conditions
Evidence
```

---

# 45. Performance Requirements

MVP target:

### API

```text
P95 < 500ms
```

cho các query không cần LLM.

### Quant Calculation

```text
1000 stocks
```

phải có khả năng tính daily features trong thời gian chấp nhận được trên một server đơn.

### AI Analysis

LLM latency không được xem là core API latency.

Agent execution phải có:

```text
timeout
retry
fallback
```

---

# 46. Observability

System phải theo dõi:

```text
CPU
Memory
Disk
Database
API latency
Worker status
LLM latency
LLM cost
Agent failures
Data pipeline failures
Model performance
Data freshness
```

---

# 47. Cost Control

LLM không được gọi cho các tác vụ deterministic.

Không dùng LLM để:

```text
RSI
P/E
MA
Return
Volatility
Ranking
```

LLM chỉ dùng khi cần:

```text
Interpretation
Research
Synthesis
Reasoning
Report
```

Mục tiêu:

> Minimize LLM calls while maximizing information value.

---

# 48. Development Phases

## Phase 0 — Specification

Deliverables:

```text
SYSTEM_SPECIFICATION.md
ARCHITECTURE.md
DATABASE_SCHEMA.md
```

---

## Phase 1 — Data Foundation

Deliverables:

```text
PostgreSQL
Market data
Historical data
Data validation
Data pipeline
```

---

## Phase 2 — Quant Engine

Deliverables:

```text
Technical Engine
Fundamental Engine
Valuation Engine
Risk Engine
Factor Engine
Scoring Engine
```

---

## Phase 3 — Backtesting

Deliverables:

```text
Backtesting Engine
Walk-forward
Transaction Cost
Performance Report
```

---

## Phase 4 — RAG

Deliverables:

```text
Document ingestion
Embedding
Qdrant
Hybrid retrieval
Reranking
Evidence
```

---

## Phase 5 — AI Agent

Deliverables:

```text
Research Agent
Analysis Agent
Monitoring Agent
Portfolio Agent
Orchestrator
```

---

## Phase 6 — ML

Deliverables:

```text
Feature Dataset
XGBoost / LightGBM
Prediction
Calibration
Model Registry
```

---

## Phase 7 — Production

Deliverables:

```text
FastAPI
Dashboard
Authentication
Monitoring
Alert
Audit
Docker
CI/CD
```

---

# 49. MVP Definition

MVP is considered complete when the system can:

```text
1. Load historical market data
2. Store data in PostgreSQL
3. Calculate technical indicators
4. Calculate fundamental factors
5. Calculate valuation
6. Calculate risk
7. Generate stock score
8. Rank stocks
9. Backtest ranking strategy
10. Show results on dashboard
```

Example:

```text
VN30
  ↓
Quant Engine
  ↓
Score
  ↓
Ranking
  ↓
Backtest
  ↓
Dashboard
```

LLM Agent is **not required for MVP-1**.

---

# 50. MVP-2 Definition

MVP-2 adds:

```text
News
RAG
Qdrant
Evidence
AI Analysis Agent
```

User can ask:

```text
"Phân tích FPT"
```

System returns:

```text
Quantitative Analysis
+
News Analysis
+
Investment Thesis
+
Risk
+
Evidence
```

---

# 51. MVP-3 Definition

MVP-3 adds:

```text
ML Prediction
Market Regime
Portfolio Agent
Monitoring
Alerts
Prediction Evaluation
```

---

# 52. Production Definition

Production system requires:

```text
Reliable Data
Validated Models
Backtested Strategies
Model Registry
Agent Evaluation
Observability
Audit
Security
Backup
Disaster Recovery
Cost Monitoring
```

---

# 53. Key Architectural Decisions

## ADR-001

**Decision:**

Quantitative calculations must be separated from LLM.

**Reason:**

Deterministic, testable and reproducible.

---

## ADR-002

**Decision:**

Qdrant is the initial vector database.

**Reason:**

Suitable for document/news RAG and compatible with existing vector-search architecture.

---

## ADR-003

**Decision:**

PostgreSQL/TimescaleDB is the primary structured data store.

**Reason:**

Minimize infrastructure complexity during MVP.

---

## ADR-004

**Decision:**

Kafka/Airflow are deferred.

**Reason:**

Infrastructure should scale according to actual workload.

---

## ADR-005

**Decision:**

LLM provider must be abstracted.

**Reason:**

Avoid vendor lock-in.

---

## ADR-006

**Decision:**

AI output must use structured schema.

**Reason:**

Validation, storage, API integration and reproducibility.

---

## ADR-007

**Decision:**

Backtesting is a first-class system component.

**Reason:**

Investment signals must be empirically validated.

---

# 54. Success Metrics

System success must not be measured only by:

```text
LLM response quality
```

Primary metrics:

```text
Data Quality
Prediction Calibration
Backtest Performance
Out-of-sample Performance
Drawdown
Sharpe
Signal Stability
False Positive Rate
Agent Evidence Accuracy
Hallucination Rate
```

---

# 55. Future Extensions

Potential future modules:

```text
Options Analysis
ETF Analysis
Global Markets
US Stocks
Crypto
Alternative Data
Insider Transactions
Satellite Data
Web Sentiment
Earnings Call Analysis
Portfolio Optimization
Automated Paper Trading
Broker Integration
Real-time Streaming
Reinforcement Learning
```

Các module này không thuộc scope 1.0.

---

# 56. Final System Philosophy

Hệ thống phải tuân thủ nguyên tắc:

```text
                 ┌──────────────┐
                 │    DATA      │
                 └──────┬───────┘
                        ↓
                 ┌──────────────┐
                 │    QUANT     │
                 └──────┬───────┘
                        ↓
                 ┌──────────────┐
                 │   BACKTEST   │
                 └──────┬───────┘
                        ↓
                 ┌──────────────┐
                 │     ML       │
                 └──────┬───────┘
                        ↓
                 ┌──────────────┐
                 │     RAG      │
                 └──────┬───────┘
                        ↓
                 ┌──────────────┐
                 │  AI AGENT    │
                 └──────┬───────┘
                        ↓
                 ┌──────────────┐
                 │   EVIDENCE   │
                 └──────┬───────┘
                        ↓
                 ┌──────────────┐
                 │ RISK CONTROL │
                 └──────┬───────┘
                        ↓
                 ┌──────────────┐
                 │    HUMAN     │
                 └──────────────┘
```

Core principle:

> **AI does not replace investment judgment. AI increases the speed, consistency, depth and traceability of investment research.**

---

# 57. Immediate Next Steps

Sau khi `SYSTEM_SPECIFICATION.md` được chấp thuận, thứ tự triển khai chính thức là:

```text
STEP 1
SYSTEM SPECIFICATION
        ↓
STEP 2
DATABASE DESIGN
        ↓
STEP 3
REPOSITORY / PROJECT STRUCTURE
        ↓
STEP 4
DATA SOURCE DESIGN
        ↓
STEP 5
DATA INGESTION
        ↓
STEP 6
QUANT ENGINE
        ↓
STEP 7
BACKTEST ENGINE
        ↓
STEP 8
RAG
        ↓
STEP 9
AI AGENT
        ↓
STEP 10
ML PREDICTION
        ↓
STEP 11
PORTFOLIO INTELLIGENCE
        ↓
STEP 12
PRODUCTION
```

**Không chuyển sang Agent trước khi Data + Quant + Backtest đạt baseline có thể kiểm chứng.**

---

# 58. Current Project Status

```text
Specification:
        ████████████████████ 100%

Architecture:
        ███████████████░░░░░  75%

Database:
        ░░░░░░░░░░░░░░░░░░░░   0%

Data Pipeline:
        ░░░░░░░░░░░░░░░░░░░░   0%

Quant Engine:
        ░░░░░░░░░░░░░░░░░░░░   0%

Backtesting:
        ░░░░░░░░░░░░░░░░░░░░   0%

RAG:
        ░░░░░░░░░░░░░░░░░░░░   0%

AI Agent:
        ░░░░░░░░░░░░░░░░░░░░   0%

ML:
        ░░░░░░░░░░░░░░░░░░░░   0%

Production:
        ░░░░░░░░░░░░░░░░░░░░   0%
```

**Next artifact:**

```text
DATABASE_SCHEMA.md
```

Database schema sẽ được thiết kế trực tiếp từ specification này, sau đó mới bắt đầu viết code.