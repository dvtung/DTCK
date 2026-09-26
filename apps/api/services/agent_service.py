"""Agent orchestrator dependency (T013) — process-wide singleton.

Binds the deterministic ``ToolCatalog`` (MarketService + RagService) to the
``Orchestrator`` and keeps one in-memory ``AuditTrail`` for the process so
``GET /api/v1/agents/runs`` reflects the runs the API actually executed.

When ``LLM_PROVIDER`` is not ``mock`` the orchestrator also receives the
provider-abstracted LLM client (ADR-005) so the Analysis Agent can synthesize
its §25 investment thesis in natural language.  Quant numbers keep coming from
the deterministic engine — the LLM only *reasons over* them (§4/§47).
"""

from __future__ import annotations

from functools import lru_cache

from apps.api.config import settings
from apps.api.dependencies import get_market_service
from apps.api.services.rag_service import get_rag_service
from src.agents.llm.client import LLMClient, create_llm_client
from src.agents.orchestrator.agent import AuditTrail, Orchestrator
from src.agents.tools import ToolCatalog

DETERMINISTIC_PROVIDERS = frozenset({"mock", "none", ""})
BASELINE_TIMEOUT_S = 30.0


@lru_cache
def get_audit_trail() -> AuditTrail:
    """Process-wide §31 run audit store."""
    return AuditTrail()


@lru_cache
def get_llm_client() -> LLMClient | None:
    """LLM client for agent reasoning — ``None`` keeps the baseline deterministic.

    ``LLM_PROVIDER=mock`` (the test/offline default) never constructs a network
    client, so the unit suite and the DB-free fixture stay reproducible.
    """
    provider = (settings.llm_provider or "mock").strip().lower()
    if provider in DETERMINISTIC_PROVIDERS:
        return None
    return create_llm_client(
        provider,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        timeout_seconds=float(settings.llm_timeout_seconds),
        api_key=settings.llm_api_key,
        think=settings.llm_think,
    )


@lru_cache
def get_orchestrator() -> Orchestrator:
    """Provide the process-wide orchestrator bound to the app services."""
    tools = ToolCatalog(get_market_service(), get_rag_service())
    llm = get_llm_client()
    # LLM turns are far slower than the deterministic tool calls, so the §45
    # run budget must clear the client timeout (otherwise every run "times out").
    timeout_s = BASELINE_TIMEOUT_S if llm is None else float(settings.llm_timeout_seconds) + 15.0
    return Orchestrator(tools, audit=get_audit_trail(), llm=llm, timeout_s=timeout_s)


__all__ = ["get_audit_trail", "get_llm_client", "get_orchestrator"]
