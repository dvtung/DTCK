"""Agent structured output (§23) and audit records (§13/§31).

All agent outputs MUST validate against these Pydantic schemas before they
leave the orchestrator (ADR-006).  ``InvestmentAnalysis`` mirrors the §23
example; ``AgentRunRecord`` / ``AgentToolCallRecord`` mirror the agent_runs /
agent_tool_calls tables (§13.2/§13.3).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# §23 — structured agent output


class InvestmentAnalysis(BaseModel):
    """One symbol's full investment analysis (§23/§25).

    Scores come EXCLUSIVELY from the quant engine via tools — never computed
    by the agent itself (§47).  ``evidence`` carries the §19 objects that back
    the thesis (ADR-006, §43).
    """

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
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AgentAlert(BaseModel):
    """A monitoring alert (§20.3 / §42 guardrail ladder)."""

    alert_type: str
    severity: str  # normal | warning | critical
    symbol: str
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PortfolioPosition(BaseModel):
    """One input position for the Portfolio Agent (§20.4/§27)."""

    symbol: str
    quantity: float
    cost_basis: float | None = None


class PortfolioRiskSnapshot(BaseModel):
    """Portfolio-level analysis (§20.4 — separate from stock ranking §27)."""

    total_value: float
    positions: int
    top_concentration_pct: float
    max_sector_pct: float
    avg_score: float
    max_drawdown_est: float
    risk_budget_used_pct: float
    warnings: list[str] = Field(default_factory=list)
    alerts: list[AgentAlert] = Field(default_factory=list)


class ResearchBrief(BaseModel):
    """Research Agent output (§20.1): profile + evidence + key facts."""

    symbol: str
    profile: dict[str, Any] = Field(default_factory=dict)
    key_facts: list[str] = Field(default_factory=list)
    important_events: list[str] = Field(default_factory=list)
    news: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)


class MonitoringReport(BaseModel):
    """Monitoring Agent output (§20.3): alerts raised over a symbol set."""

    symbols: list[str] = Field(default_factory=list)
    alerts: list[AgentAlert] = Field(default_factory=list)
    critical: int = 0
    warnings_count: int = 0
    normal: int = 0


# ---------------------------------------------------------------------------
# §13/§31 — audit records


class AgentToolCallRecord(BaseModel):
    """One tool invocation inside an agent run (§22, §31)."""

    tool_name: str
    tool_input: dict[str, Any] = Field(default_factory=dict)
    tool_output: dict[str, Any] = Field(default_factory=dict)
    called_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    latency_ms: int = 0


class AgentRunRecord(BaseModel):
    """Full audit trail of one executor run (§13.2, §31)."""

    agent_run_id: UUID = Field(default_factory=uuid4)
    user_request: str
    agent_id: str
    agent_version: str
    model: str
    model_version: str | None = None
    prompt_version: str | None = None
    plan: list[str] = Field(default_factory=list)
    tools_called: list[AgentToolCallRecord] = Field(default_factory=list)
    final_output: dict[str, Any] | None = None
    status: str = "running"  # running | succeeded | failed
    attempts: int = 1  # §45 retry bookkeeping
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    latency_ms: int = 0
    token_usage: dict[str, Any] | None = None


__all__ = [
    "AgentAlert",
    "AgentRunRecord",
    "AgentToolCallRecord",
    "InvestmentAnalysis",
    "MonitoringReport",
    "PortfolioPosition",
    "PortfolioRiskSnapshot",
    "ResearchBrief",
]
