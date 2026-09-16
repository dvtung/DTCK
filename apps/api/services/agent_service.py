"""Agent orchestrator dependency (T013) — process-wide singleton.

Binds the deterministic ``ToolCatalog`` (MarketService + RagService) to the
``Orchestrator`` and keeps one in-memory ``AuditTrail`` for the process so
``GET /api/v1/agents/runs`` reflects the runs the API actually executed.
"""

from __future__ import annotations

from functools import lru_cache

from apps.api.dependencies import get_market_service
from apps.api.services.rag_service import get_rag_service
from src.agents.orchestrator.agent import AuditTrail, Orchestrator
from src.agents.tools import ToolCatalog


@lru_cache
def get_audit_trail() -> AuditTrail:
    """Process-wide §31 run audit store."""
    return AuditTrail()


@lru_cache
def get_orchestrator() -> Orchestrator:
    """Provide the process-wide orchestrator bound to the app services."""
    tools = ToolCatalog(get_market_service(), get_rag_service())
    return Orchestrator(tools, audit=get_audit_trail())


__all__ = ["get_audit_trail", "get_orchestrator"]
