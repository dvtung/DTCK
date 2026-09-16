"""Research Agent (§20.1) — company profile + news + §19 evidence.

Deterministic: every fact comes from a tool call (§22) — the agent assembles a
reproducible brief, it does not invent company data (§47).  The LangGraph/LLM
layer stays optional (`pyproject` extra `agents`).
"""

from __future__ import annotations

from typing import Any

from src.agents.schemas import ResearchBrief
from src.agents.tools import ToolCatalog
from src.agents.util import clamp01, matches_important_news, round_score

PLAN: list[str] = [
    "Company profile",
    "Price & valuation",
    "Fundamental quality",
    "Peer comparison",
    "News",
    "Corporate events",
    "Evidence",
]

TOOLS: tuple[str, ...] = (
    "get_stock_profile",
    "get_stock_price",
    "get_fundamentals",
    "get_valuation",
    "get_peer_analysis",
    "get_news",
    "get_corporate_events",
    "search_evidence",
)


class ResearchAgent:
    """Collects profile facts, news and evidence for one symbol (§20.1)."""

    def __init__(
        self,
        tools: ToolCatalog,
        *,
        agent_id: str = "research",
        version: str = "1.0",
    ) -> None:
        self._tools = tools
        self.agent_id = agent_id
        self.version = version

    def research(self, symbol: str, *, query: str = "") -> ResearchBrief:
        """Build a research brief for ``symbol`` (raises on unknown symbol)."""
        profile = self._tools.call("get_stock_profile", symbol=symbol)
        if not profile.get("available"):
            raise ValueError(f"symbol '{symbol}' has no profile (unknown symbol?)")
        price = self._tools.call("get_stock_price", symbol=symbol)
        fundamentals = self._tools.call("get_fundamentals", symbol=symbol)
        valuation = self._tools.call("get_valuation", symbol=symbol)
        peers = self._tools.call("get_peer_analysis", symbol=symbol)
        news = self._tools.call("get_news", symbol=symbol, top_k=5)
        events = self._tools.call("get_corporate_events", symbol=symbol)
        evidence = self._tools.call(
            "search_evidence",
            query=query or f"{symbol} company profile news",
            top_k=4,
        )

        items = [n for n in (news.get("news") or []) if isinstance(n, dict)]
        important = [
            f"{n.get('title', '')} ({n.get('source', 'unknown source')})"
            for n in items
            if matches_important_news(str(n.get("title", "")))
        ]
        evs = [e for e in (evidence.get("evidence") or []) if isinstance(e, dict)]
        warnings: list[str] = []
        if not events.get("available"):
            warnings.append("Corporate-events feed not wired (T012 news only).")
        if not evs:
            warnings.append("No evidence retrieved for the research query.")

        return ResearchBrief(
            symbol=symbol.upper(),
            profile={k: v for k, v in profile.items() if k != "available"},
            key_facts=self._key_facts(profile, price, fundamentals, valuation, peers),
            important_events=important,
            news=items,
            evidence=evs,
            confidence=self._confidence(evs),
            warnings=warnings,
        )

    @staticmethod
    def _key_facts(
        profile: dict[str, Any],
        price: dict[str, Any],
        fundamentals: dict[str, Any],
        valuation: dict[str, Any],
        peers: dict[str, Any],
    ) -> list[str]:
        """Deterministic fact lines, each traced to a tool payload."""
        facts = [
            f"{profile.get('company_name')} ({profile.get('symbol')}) trades on "
            f"{profile.get('exchange')} in the {profile.get('sector')} sector "
            f"({profile.get('industry')})."
        ]
        if price.get("available"):
            facts.append(
                f"Last close {price.get('price')} "
                f"({round_score(price.get('change_pct'), 4):+.2%}); 20-day range "
                f"{price.get('low_20')}-{price.get('high_20')}; "
                f"volume {price.get('volume')} (avg {price.get('volume_avg_20')})."
            )
        if fundamentals.get("available"):
            facts.append(
                f"Data-quality score "
                f"{round_score(fundamentals.get('overall_score')):.1f}/100 "
                f"(below_threshold={fundamentals.get('below_threshold')})."
            )
        pe, pb = valuation.get("pe"), valuation.get("pb")
        if pe is not None and pb is not None:
            facts.append(
                f"Valuation: P/E {pe}, P/B {pb}, dividend yield {valuation.get('dividend_yield')}."
            )
        if peers.get("count"):
            facts.append(
                f"{peers.get('count')} {peers.get('sector')} peers average "
                f"{peers.get('average_score')}."
            )
        return facts

    @staticmethod
    def _confidence(evidence: list[dict[str, Any]]) -> float:
        """Mean §19 evidence confidence (0 when nothing was retrieved)."""
        if not evidence:
            return 0.0
        scores = [round_score(e.get("confidence"), 4) for e in evidence]
        return clamp01(round(sum(scores) / len(scores), 4))


__all__ = ["PLAN", "TOOLS", "ResearchAgent"]
