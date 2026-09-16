# AGENT ARCHITECTURE

## AI Investment Research & Decision Intelligence Platform

**Version:** 1.0
**Status:** IMPLEMENTED (T013, 2026-09-16) — deterministic, offline, no LLM. The orchestrator resolves tasks through the registry, builds the §21 plan, calls tools (ToolCatalog wrapping MarketService/RagService), audits each run (§31), and supports retry/timeout/failure per §45. LangGraph is the planned Phase-5 upgrade path (§34) for LLM-backed planning; the current baseline is intentionally LLM-free to satisfy the spec §57 ordering gate.

---

# 1. When Agents Act (critical ordering, spec §57)

**Agents are OFF until Data + Quant + Backtest reach a verifiable baseline (MVP-1).**

```text
MVP-1: data → quant → score → ranking → backtest → dashboard     (NO LLM)
MVP-2: + news/RAG/evidence + Analysis Agent
MVP-3: + ML prediction + market regime + Portfolio Agent + monitoring + alerts
```

---

# 2. Framework

- **LangGraph** planned for stateful, controllable agent orchestration (§34) — Phase-5 upgrade path when LLM backing is enabled. MVP-1/T013 baseline uses a deterministic orchestrator (no LLM) that resolves a §21 plan, calls tools, and records §31 audit.
- **LLM provider abstraction** (ADR-005) — no vendor lock-in.
- Every agent output follows a **Pydantic schema** (ADR-006, §23).

---

# 3. Agents (§20)

## 3.1. Research Agent
- Find information, synthesize company profile, collect evidence, surface important events.
- Heavy use of RAG tools + news/corporate events retrieval.

## 3.2. Analysis Agent
- Analyze one symbol: call Quant Tools, RAG Tools, synthesize evidence → build investment thesis.
- Produces `InvestmentAnalysis` (§23) with scores, thesis, catalysts, risks, invalidation conditions, confidence, evidence.

## 3.3. Monitoring Agent
- Track price/volume/news/events/fundamental/risk changes.
- Emits alerts on: signal change, risk increase, important news, technical breakout, fundamental deterioration (§20.3).

## 3.4. Portfolio Agent
- Position sizing, correlation, sector exposure, portfolio risk, concentration, drawdown, risk budget (§20.4, §27).
- Portfolio decisions are **separate** from stock ranking (§27).

## 3.5. Orchestrator (§21)
- Central coordinator. Example plan for "Phân tích FPT":

```text
1. Market regime   6. Peer comparison   10. ML prediction
2. Price           7. News             11. Investment thesis
3. Technical       8. Corporate events
4. Fundamental     9. Risk              (+ evidence)
5. Valuation
```

---

# 4. Tool Architecture (§22)

LLM → Tool Call → Application Service → (DB / Quant Engine / RAG) → Structured Result → LLM.

**LLM never accesses the database directly.**

Tool catalog (MVP): `get_stock_price`, `get_technical`, `get_fundamentals`, `get_valuation`, `get_peer_analysis`, `get_market_regime`, `get_news`, `get_corporate_events`, `get_prediction`, `get_risk`.

---

# 5. Structured Output (§23)

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

# 6. Confidence Model (§24)

Confidence combines: model calibration, data quality, signal agreement, market regime + **(optionally) agent agreement**. Always risk-adjusted by guardrails (§42).

---

# 7. Audit & Governance

- Every run → `agent_runs` (user_request, agent, model/version, prompts, final_output, latency, tokens) (§31).
- Every tool call → `agent_tool_calls` (tool, input, output) (§22).
- Agent registry → `agent_registry` (version, prompt version, tools, allowed data, output schema, eval score, status) (§41).

**Agents are FORBIDDEN from (§41):** changing DB schema, changing models, changing scoring weights, executing trades, deleting audit logs.

---

# 8. LLM Guardrails (§4.3, §47)

- LLM must **never** compute RSI/P/E/MA/returns/volatility/ranking — those come only from tools.
- LLM must **never** fabricate financial figures (spec §3 non-objective).
- Output must be validated against schema; invalid outputs → retry with fallback → failure.
- Timeout + retry + fallback are mandatory for agent execution (§45).

---

# 9. MVP-2 Definition (§50)

User asks "Phân tích FPT" → system returns Quantitative Analysis + News Analysis + Investment Thesis + Risk + Evidence.