# Memory Bank — Project Context

## AI Investment Research & Decision Intelligence Platform (DTCK)

**Last updated:** 2026-09-06

---

## 1. What We Are Building

A research & decision-intelligence platform for the **Vietnamese stock market** (HOSE / HNX / UPCOM), starting with the VN30 universe, that:

1. Collects & validates market, fundamental, valuation, news, macro and corporate-event data.
2. Runs deterministic quantitative analysis (technical, fundamental, valuation, momentum, risk).
3. Scores & ranks stocks; backtests strategies before they can emit signals.
4. (Later) adds RAG evidence, ML prediction, and agentic AI research layered on top.

**The system is NOT an automated investment decision maker.** It supports a human decision: `AI Analysis → Risk Validation → Human Review → Investment Decision` (§4.6).

---

## 2. Non-Objectives (§3, keep visible)

- No guarantee of profit; no absolute price prediction; no replacement of investment experts; no auto-trading; no LLM-fabricated financial figures; no LLM-only BUY/SELL calls.

---

## 3. Core Philosophy (spec §56)

> **AI does not replace investment judgment. AI increases the speed, consistency, depth and traceability of investment research.**

Pipeline: `DATA → QUANT → BACKTEST → ML → RAG → AI AGENT → EVIDENCE → RISK CONTROL → HUMAN`

---

## 4. Governing Design Principles (§4)

1. **Data First** — bad data ⇒ bad features ⇒ bad model ⇒ bad agent.
2. **Deterministic Calculation First** — RSI/P/E/ROE/etc. always computed by software, never by LLM.
3. **LLM Is a Reasoning Layer** — plans, selects tools, synthesizes; never a source of truth.
4. **Evidence-Based Reasoning** — claims → evidence → source → timestamp → data version.
5. Backtest before deployment; human-in-the-loop; full auditability.

---

## 5. Key Numbers

| Item | Value |
|---|---|
| Market | Vietnam (HOSE, HNX, UPCOM) |
| Initial universe | VN30 → VN100 → full market |
| Horizons | Short 1–20 TD, Medium 1–6 m, Long 6–36 m |
| Baseline scoring weights | Fund 30 / Tech 20 / Mom 15 / Val 15 / Qual 10 / Risk 10 |
| API perf target | P95 < 500 ms (non-LLM) |

---

## 6. Architecture in One Paragraph

FastAPI (API) + Streamlit (MVP dashboard) + Worker (schedulers/ingestion) over **PostgreSQL/TimescaleDB** (structured, hypertables) + **Qdrant** (vector search). A deterministic **Quant Engine** produces versioned features/factor scores; a **Backtesting Engine** validates strategies; later phases add ML (XGBoost/LightGBM), RAG, and LangGraph agents behind a tool layer — the LLM never touches the DB directly and never computes numbers.

See `docs/ARCHITECTURE.md` for the full picture.

---

## 7. Key References

| Doc | Path |
|---|---|
| System specification | `docs/SYSTEM_SPECIFICATION.md` |
| Concept draft (Vietnamese) | `docs/AI_INVESTMENT_CONCEPT.md` |
| Architecture | `docs/ARCHITECTURE.md` |
| Data architecture | `docs/DATA_ARCHITECTURE.md` |
| Database schema | `docs/DATABASE_SCHEMA.md` |
| Quant engine | `docs/QUANT_ENGINE.md` |
| Backtesting | `docs/BACKTESTING.md` |
| ML | `docs/ML_ARCHITECTURE.md` |
| RAG | `docs/RAG_ARCHITECTURE.md` |
| Agents | `docs/AGENT_ARCHITECTURE.md` |
| API | `docs/API_SPECIFICATION.md` |
| Deployment | `docs/DEPLOYMENT.md` |
| Security | `docs/SECURITY.md` |
| Memory bank index | `memory-bank/README.md` (see below) |