"""Orchestrator (§21) + agent registry (§41) + run audit (§13.2/§31).

Central coordinator: it resolves a *task* through the registry, builds the §21
plan, executes the matching agent, mirrors every tool call into
``AgentRunRecord.tools_called`` (§22) and stores the finished run in an
``AuditTrail`` that mirrors the ``agent_runs`` / ``agent_tool_calls`` tables.

Execution is deterministic and offline (no LLM required).  §45's
timeout/retry/fallback contract is implemented as an attempt loop plus an
optional wall-clock timeout; ``fallback`` is the structured *failed* run record
(never a silent success).
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import TYPE_CHECKING, Any
from uuid import UUID

from src.agents.analysis.agent import PLAN as ANALYSIS_PLAN
from src.agents.analysis.agent import TOOLS as ANALYSIS_TOOLS
from src.agents.analysis.agent import AnalysisAgent
from src.agents.monitoring.agent import PLAN as MONITORING_PLAN
from src.agents.monitoring.agent import (
    SEVERITY_CRITICAL,
    SEVERITY_NORMAL,
    SEVERITY_WARNING,
    MonitoringAgent,
)
from src.agents.monitoring.agent import TOOLS as MONITORING_TOOLS
from src.agents.portfolio.agent import PLAN as PORTFOLIO_PLAN
from src.agents.portfolio.agent import TOOLS as PORTFOLIO_TOOLS
from src.agents.portfolio.agent import PortfolioAgent
from src.agents.research.agent import PLAN as RESEARCH_PLAN
from src.agents.research.agent import TOOLS as RESEARCH_TOOLS
from src.agents.research.agent import ResearchAgent
from src.agents.schemas import (
    AgentRunRecord,
    MonitoringReport,
    PortfolioPosition,
)
from src.agents.tools import ToolCatalog

if TYPE_CHECKING:
    from pydantic import BaseModel

MODEL = "deterministic-quant-v1"
TASK_ANALYZE = "analyze"
TASK_RESEARCH = "research"
TASK_MONITOR = "monitor"
TASK_PORTFOLIO = "portfolio"

DEFAULT_ALLOWED_DATA: tuple[str, ...] = (
    "market_data",
    "fundamental_data",
    "valuation_data",
    "news",
    "rag_index",
)


class AgentTimeoutError(RuntimeError):
    """Raised when an agent run exceeds its configured timeout (§45)."""


@dataclass(frozen=True)
class AgentSpec:
    """Registry entry mirroring the ``agent_registry`` table (§13.1/§41)."""

    agent_id: str
    version: str
    system_prompt_version: str
    output_schema: str
    task: str
    plan: tuple[str, ...]
    available_tools: tuple[str, ...]

    allowed_data: tuple[str, ...] = DEFAULT_ALLOWED_DATA
    status: str = "active"
    evaluation_score: float | None = None

    def to_payload(self) -> dict[str, Any]:
        """Serialise the spec for the ``GET /api/v1/agents`` listing."""
        return {
            "agent_id": self.agent_id,
            "version": self.version,
            "system_prompt_version": self.system_prompt_version,
            "output_schema": self.output_schema,
            "task": self.task,
            "plan": list(self.plan),
            "available_tools": list(self.available_tools),
            "allowed_data": list(self.allowed_data),
            "status": self.status,
            "evaluation_score": self.evaluation_score,
        }


class AgentRegistry:
    """Task → agent definition registry (§41)."""

    def __init__(self) -> None:
        self._specs: dict[str, AgentSpec] = {}

    def register(self, spec: AgentSpec) -> None:
        self._specs[spec.task] = spec

    def get(self, task: str) -> AgentSpec:
        try:
            return self._specs[task]
        except KeyError as exc:
            raise ValueError(f"unknown agent task '{task}'") from exc

    def tasks(self) -> list[str]:
        return sorted(self._specs)

    def to_payload(self) -> list[dict[str, Any]]:
        return [self._specs[t].to_payload() for t in self.tasks()]


def build_default_registry() -> AgentRegistry:
    """Register the four §20 agents with their plans, tools and schemas."""
    registry = AgentRegistry()
    registry.register(
        AgentSpec(
            agent_id="analysis",
            version="1.0",
            system_prompt_version="analysis-prompt-v1",
            output_schema="InvestmentAnalysis",
            task=TASK_ANALYZE,
            plan=tuple(ANALYSIS_PLAN),
            available_tools=ANALYSIS_TOOLS,
        )
    )
    registry.register(
        AgentSpec(
            agent_id="research",
            version="1.0",
            system_prompt_version="research-prompt-v1",
            output_schema="ResearchBrief",
            task=TASK_RESEARCH,
            plan=tuple(RESEARCH_PLAN),
            available_tools=RESEARCH_TOOLS,
        )
    )
    registry.register(
        AgentSpec(
            agent_id="monitoring",
            version="1.0",
            system_prompt_version="monitoring-prompt-v1",
            output_schema="MonitoringReport",
            task=TASK_MONITOR,
            plan=tuple(MONITORING_PLAN),
            available_tools=MONITORING_TOOLS,
        )
    )
    registry.register(
        AgentSpec(
            agent_id="portfolio",
            version="1.0",
            system_prompt_version="portfolio-prompt-v1",
            output_schema="PortfolioRiskSnapshot",
            task=TASK_PORTFOLIO,
            plan=tuple(PORTFOLIO_PLAN),
            available_tools=PORTFOLIO_TOOLS,
        )
    )
    return registry


class AuditTrail:
    """In-memory §31 audit store (agent_runs + agent_tool_calls)."""

    def __init__(self, max_records: int = 200) -> None:
        self._runs: dict[UUID, AgentRunRecord] = {}
        self._order: list[UUID] = []
        self._latest_analysis: dict[str, UUID] = {}
        self._max_records = max_records

    def record(self, run: AgentRunRecord) -> None:
        """Insert or refresh a run record, trimming the oldest beyond the cap."""
        if run.agent_run_id not in self._runs:
            self._order.append(run.agent_run_id)
        self._runs[run.agent_run_id] = run
        output = run.final_output or {}
        if run.agent_id == "analysis" and run.status == "succeeded" and output:
            self._latest_analysis[str(output.get("symbol", ""))] = run.agent_run_id
        while len(self._order) > self._max_records:
            expired = self._order.pop(0)
            self._runs.pop(expired, None)
            self._latest_analysis = {
                symbol: run_id
                for symbol, run_id in self._latest_analysis.items()
                if run_id != expired
            }

    def get(self, run_id: UUID) -> AgentRunRecord | None:
        return self._runs.get(run_id)

    def list_runs(self, *, agent_id: str | None = None, limit: int = 50) -> list[AgentRunRecord]:
        """Newest-first run history, optionally filtered by agent id (§31)."""
        runs = [self._runs[i] for i in reversed(self._order)]
        if agent_id:
            runs = [r for r in runs if r.agent_id == agent_id]
        return runs[:limit]

    def latest_analysis(self, symbol: str) -> AgentRunRecord | None:
        """Most recent successful analysis run for ``symbol`` (§2.7 API)."""
        run_id = self._latest_analysis.get(symbol.upper())
        return self._runs.get(run_id) if run_id else None

    def clear(self) -> None:
        """Drop all records (test/operative helper)."""
        self._runs.clear()
        self._order.clear()
        self._latest_analysis.clear()

    def __len__(self) -> int:
        return len(self._order)


class Orchestrator:
    """Runs agent tasks with a plan, tool-call audit and retry/timeout (§21/§31/§45)."""

    def __init__(
        self,
        tools: ToolCatalog,
        *,
        audit: AuditTrail | None = None,
        registry: AgentRegistry | None = None,
        max_attempts: int = 2,
        timeout_s: float | None = 30.0,
    ) -> None:
        self._tools = tools
        self._audit = audit if audit is not None else AuditTrail()
        self._registry = registry if registry is not None else build_default_registry()
        self._analysis = AnalysisAgent(tools)
        self._research = ResearchAgent(tools)
        self._monitoring = MonitoringAgent(tools)
        self._portfolio = PortfolioAgent(tools)
        self._max_attempts = max(1, max_attempts)
        self._timeout_s = timeout_s
        self._deferred: dict[
            UUID, tuple[Callable[[dict[str, Any]], BaseModel], dict[str, Any], AgentRunRecord]
        ] = {}
        self._handlers: dict[str, Callable[[dict[str, Any]], BaseModel]] = {
            TASK_ANALYZE: self._run_analyze,
            TASK_RESEARCH: self._run_research,
            TASK_MONITOR: self._run_monitor,
            TASK_PORTFOLIO: self._run_portfolio,
        }

    # ----------------------------------------------------------- accessors
    @property
    def audit(self) -> AuditTrail:
        return self._audit

    @property
    def registry(self) -> AgentRegistry:
        return self._registry

    @property
    def tools(self) -> ToolCatalog:
        return self._tools

    def plan_for(self, task: str) -> list[str]:
        """§21 plan published by the registry for ``task``."""
        return list(self._registry.get(task).plan)

    # ------------------------------------------------------------ handlers
    def _run_analyze(self, params: dict[str, Any]) -> BaseModel:
        return self._analysis.analyze(str(params["symbol"]).upper())

    def _run_research(self, params: dict[str, Any]) -> BaseModel:
        return self._research.research(
            str(params["symbol"]).upper(), query=str(params.get("query") or "")
        )

    def _run_monitor(self, params: dict[str, Any]) -> BaseModel:
        symbols = [str(s).upper() for s in params.get("symbols") or []]
        previous = params.get("previous_signals") or {}
        alerts = self._monitoring.monitor(symbols, previous_signals=dict(previous))
        return MonitoringReport(
            symbols=symbols,
            alerts=alerts,
            critical=sum(1 for a in alerts if a.severity == SEVERITY_CRITICAL),
            warnings_count=sum(1 for a in alerts if a.severity == SEVERITY_WARNING),
            normal=sum(1 for a in alerts if a.severity == SEVERITY_NORMAL),
        )

    def _run_portfolio(self, params: dict[str, Any]) -> BaseModel:
        positions = [PortfolioPosition(**p) for p in params.get("positions") or []]
        budget = params.get("risk_budget_annual_vol")
        if budget is None:
            return self._portfolio.analyze(positions)
        return self._portfolio.analyze(positions, risk_budget_annual_vol=float(budget))

    # ----------------------------------------------------------- public API
    def analyze(self, symbol: str, *, user_request: str | None = None) -> AgentRunRecord:
        """Run the §20.2 Analysis Agent for one symbol."""
        return self.run(
            TASK_ANALYZE,
            {"symbol": symbol},
            user_request=user_request or f"Phân tích {symbol.upper()}",
        )

    def research(
        self, symbol: str, *, query: str = "", user_request: str | None = None
    ) -> AgentRunRecord:
        """Run the §20.1 Research Agent for one symbol."""
        return self.run(
            TASK_RESEARCH,
            {"symbol": symbol, "query": query},
            user_request=user_request or f"Nghiên cứu {symbol.upper()}",
        )

    def monitor(
        self,
        symbols: list[str],
        *,
        previous_signals: dict[str, str] | None = None,
        user_request: str | None = None,
    ) -> AgentRunRecord:
        """Run the §20.3 Monitoring Agent over a watchlist."""
        return self.run(
            TASK_MONITOR,
            {"symbols": symbols, "previous_signals": previous_signals or {}},
            user_request=user_request or "Giám sát watchlist",
        )

    def portfolio(
        self,
        positions: list[PortfolioPosition],
        *,
        risk_budget_annual_vol: float | None = None,
        user_request: str | None = None,
    ) -> AgentRunRecord:
        """Run the §20.4 Portfolio Agent over a position list."""
        params: dict[str, Any] = {
            "positions": [p.model_dump() for p in positions],
        }
        if risk_budget_annual_vol is not None:
            params["risk_budget_annual_vol"] = risk_budget_annual_vol
        return self.run(TASK_PORTFOLIO, params, user_request=user_request or "Phân tích danh mục")

    def run(
        self,
        task: str,
        params: dict[str, Any],
        *,
        user_request: str | None = None,
    ) -> AgentRunRecord:
        """Execute ``task`` and return its audited ``AgentRunRecord`` (§21/§31).

        Failures are recorded (``status="failed"``, ``final_output={"error":…}``)
        instead of raising, so the caller can surface the run id and the audit
        trail keeps the evidence (§45 fallback).
        """
        run, handler = self._prepare(task, params, user_request)
        return self._execute(run, handler, params)

    def submit(
        self,
        task: str,
        params: dict[str, Any],
        *,
        user_request: str | None = None,
    ) -> AgentRunRecord:
        """Queue a run without executing it (§45 async pattern).

        Returns the pre-registered record (``status="queued"``); call
        ``execute_deferred(run_id)`` to perform it.
        """
        run, handler = self._prepare(task, params, user_request)
        run.status = "queued"
        self._audit.record(run)
        self._deferred[run.agent_run_id] = (handler, dict(params), run)
        return run

    def execute_deferred(self, run_id: UUID) -> AgentRunRecord:
        """Execute a previously submitted run (background-task entry point)."""
        try:
            handler, params, run = self._deferred.pop(run_id)
        except KeyError as exc:
            raise ValueError(f"unknown queued agent run '{run_id}'") from exc
        return self._execute(run, handler, params)

    def _prepare(
        self, task: str, params: dict[str, Any], user_request: str | None
    ) -> tuple[AgentRunRecord, Callable[[dict[str, Any]], BaseModel]]:
        """Resolve the registry entry and register a running audit record."""
        spec = self._registry.get(task)
        handler = self._handlers.get(task)
        if handler is None:
            raise ValueError(f"no handler registered for task '{task}'")
        run = AgentRunRecord(
            user_request=user_request or f"{task}: {params}",
            agent_id=spec.agent_id,
            agent_version=spec.version,
            model=MODEL,
            prompt_version=spec.system_prompt_version,
            plan=list(spec.plan),
        )
        self._audit.record(run)
        return run, handler

    def _execute(
        self,
        run: AgentRunRecord,
        handler: Callable[[dict[str, Any]], BaseModel],
        params: dict[str, Any],
    ) -> AgentRunRecord:
        """Run the handler with retry + timeout, mirroring tool calls (§45)."""
        started = perf_counter()
        output: BaseModel | None = None
        error = "unknown error"
        for attempt in range(1, self._max_attempts + 1):
            run.attempts = attempt
            run.tools_called.clear()
            run.status = "running"
            with self._tools.collect(run.tools_called):
                try:
                    output = self._invoke(handler, params)
                    break
                except Exception as exc:  # noqa: BLE001 — audited as a failed run
                    output = None
                    error = f"{type(exc).__name__}: {exc}"
        run.finished_at = datetime.now(tz=UTC)
        run.latency_ms = int((perf_counter() - started) * 1000)
        if output is None:
            run.status = "timeout" if error.startswith("AgentTimeoutError") else "failed"
            run.final_output = {"error": error}
        else:
            run.status = "succeeded"
            run.final_output = output.model_dump(mode="json")
        self._audit.record(run)
        return run

    def _invoke(
        self, handler: Callable[[dict[str, Any]], BaseModel], params: dict[str, Any]
    ) -> BaseModel:
        """Invoke the handler with the §45 wall-clock timeout (if configured)."""
        if self._timeout_s is None:
            return handler(params)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(handler, params)
            try:
                return future.result(timeout=self._timeout_s)
            except FuturesTimeoutError as exc:
                raise AgentTimeoutError(f"agent run exceeded {self._timeout_s}s (§45)") from exc


__all__ = [
    "MODEL",
    "TASK_ANALYZE",
    "TASK_MONITOR",
    "TASK_PORTFOLIO",
    "TASK_RESEARCH",
    "AgentRegistry",
    "AgentSpec",
    "AgentTimeoutError",
    "AuditTrail",
    "Orchestrator",
    "build_default_registry",
]
