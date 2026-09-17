"""T013 tests — agent tools, agents, orchestrator, audit (spec §20–§24/§31/§41).

Fully deterministic and offline: the tool catalog wraps the in-memory
``MarketService``/``RagService``, no LLM or network is involved.
"""

from __future__ import annotations

import time

import pytest

from apps.api.services.market_data import MarketService
from src.agents.analysis.agent import CONFIDENCE_WEIGHTS, AnalysisAgent
from src.agents.monitoring.agent import (
    ALERT_IMPORTANT_NEWS,
    ALERT_RISK_INCREASED,
    ALERT_SIGNAL_CHANGED,
    ALERT_TECHNICAL_BREAKOUT,
    SEVERITY_CRITICAL,
    SEVERITY_NORMAL,
    SEVERITY_WARNING,
    MonitoringAgent,
)
from src.agents.orchestrator.agent import (
    MODEL,
    TASK_ANALYZE,
    AgentRegistry,
    AgentSpec,
    AuditTrail,
    Orchestrator,
    build_default_registry,
)
from src.agents.portfolio.agent import PortfolioAgent
from src.agents.research.agent import ResearchAgent
from src.agents.schemas import AgentRunRecord, InvestmentAnalysis, PortfolioPosition
from src.agents.tools import ToolCatalog
from src.agents.util import (
    bottom_factor,
    clamp01,
    matches_important_news,
    round_score,
    signal_word,
    top_factor,
)
from src.rag.service import RagService


def _tools() -> ToolCatalog:
    """Tool catalog over deterministic in-memory services."""
    market = MarketService()
    rag = RagService()
    rag.ingest_news_items(market.list_news())
    return ToolCatalog(market, rag)


def _orchestrator(**kwargs: object) -> Orchestrator:
    return Orchestrator(_tools(), **kwargs)


def _analysis() -> InvestmentAnalysis:
    """Minimal valid §23 output (used by retry/timeout tests)."""
    return InvestmentAnalysis(
        symbol="FPT",
        overall_score=61.0,
        market_regime="BULL",
        technical_score=50.0,
        fundamental_score=60.0,
        valuation_score=55.0,
        momentum_score=58.0,
        risk_score=45.0,
        thesis="stub thesis",
        catalysts=["catalyst"],
        risks=["risk"],
        invalidation_conditions=["invalidation"],
        confidence=0.6,
        evidence=[],
    )


class TestUtil:
    def test_round_score_coercions(self) -> None:
        assert round_score(None) == 0.0
        assert round_score("12.345") == 12.35
        assert round_score("nope") == 0.0
        assert round_score(1.23456, 4) == 1.2346

    def test_clamp01(self) -> None:
        assert clamp01(-1.0) == 0.0
        assert clamp01(0.4) == 0.4
        assert clamp01(2.0) == 1.0

    def test_signal_word(self) -> None:
        assert signal_word("POSITIVE") == "positive"
        assert signal_word("negative") == "negative"
        assert signal_word("??") == "neutral"

    def test_top_and_bottom_factor(self) -> None:
        contributions = {"fundamental": 0.5, "technical": 0.1, "valuation": None}
        assert top_factor(contributions)[0] == "fundamental"
        assert bottom_factor(contributions)[0] == "technical"
        assert top_factor({}) == ("", 0.0)
        assert bottom_factor({}) == ("", 0.0)

    def test_important_news_scan(self) -> None:
        assert matches_important_news("FPT bị xử phạt vi phạm công bố thông tin")
        assert matches_important_news("VCB downgrade by broker")
        assert not matches_important_news("VNINDEX adjustments continue")


class TestToolCatalog:
    def test_catalog_covers_spec_tools(self) -> None:
        catalog = _tools().catalog
        for tool in (
            "get_stock_price",
            "get_technical",
            "get_fundamentals",
            "get_valuation",
            "get_peer_analysis",
            "get_market_regime",
            "get_news",
            "get_corporate_events",
            "get_prediction",
            "get_risk",
        ):
            assert tool in catalog

    def test_price_payload(self) -> None:
        payload = _tools().call("get_stock_price", symbol="FPT")
        assert payload["available"] is True
        assert payload["price"] > 0
        assert payload["high_20"] >= payload["low_20"]
        assert payload["volume_avg_20"] > 0

    def test_regime_and_technical(self) -> None:
        tools = _tools()
        assert tools.call("get_market_regime")["regime"] in (
            "BULL",
            "BEAR",
            "SIDEWAYS",
            "VOLATILE",
        )
        assert set(tools.call("get_technical", symbol="FPT")["series"]) == {
            "sma20",
            "ema12",
            "rsi14",
        }

    def test_fundamentals_valuation_risk(self) -> None:
        tools = _tools()
        fundamentals = tools.call("get_fundamentals", symbol="FPT")
        assert fundamentals["overall_score"] > 0
        assert fundamentals["dimensions"]
        assert tools.call("get_valuation", symbol="FPT")["pe"] is not None
        risk = tools.call("get_risk", symbol="FPT")
        assert risk["risk_score"] is not None
        assert risk["annualized_volatility"] is not None

    def test_peers_and_ranking(self) -> None:
        tools = _tools()
        peers = tools.call("get_peer_analysis", symbol="VCB")
        assert peers["count"] >= 1
        assert peers["average_score"] is not None
        ranking = tools.call("get_ranking", symbol="VCB")
        assert ranking["contributions"]
        assert ranking["signal"] in ("POSITIVE", "NEUTRAL", "NEGATIVE")

    def test_evidence_search(self) -> None:
        payload = _tools().call("search_evidence", query="FPT lợi nhuận", top_k=3)
        assert payload["count"] >= 1
        assert "confidence" in payload["evidence"][0]

    def test_unknown_symbol_payloads(self) -> None:
        tools = _tools()
        for tool in (
            "get_stock_price",
            "get_stock_profile",
            "get_technical",
            "get_fundamentals",
            "get_valuation",
            "get_peer_analysis",
            "get_ranking",
            "get_risk",
        ):
            assert tools.call(tool, symbol="NOPE")["available"] is False

    def test_not_wired_tools_are_honest(self) -> None:
        tools = _tools()
        result = tools.call("get_prediction", symbol="FPT")
        assert result["available"] is True
        assert 0.0 <= result["probability_positive"] <= 1.0
        assert tools.call("get_corporate_events", symbol="FPT")["events"] == []

    def test_unknown_tool_and_bad_args(self) -> None:
        tools = _tools()
        with pytest.raises(ValueError, match="unknown tool"):
            tools.call("get_nothing")
        with pytest.raises(ValueError, match="invalid arguments"):
            tools.call("get_stock_price")

    def test_private_helpers_are_not_callable(self) -> None:
        """Only §22 catalog tools are reachable — no ``getattr`` escape hatch."""
        tools = _tools()
        for name in ("_peer_symbols", "_record", "_market", "_rag"):
            with pytest.raises(ValueError, match="unknown tool"):
                tools.call(name)

    def test_collect_records_tool_calls(self) -> None:
        tools = _tools()
        sink: list[object] = []
        with tools.collect(sink):
            tools.call("get_stock_price", symbol="FPT")
            tools.call("get_market_regime")
        assert len(sink) == 2
        first = sink[0]
        assert first.tool_name == "get_stock_price"  # type: ignore[attr-defined]
        assert first.tool_input == {"symbol": "FPT"}  # type: ignore[attr-defined]
        assert first.latency_ms >= 0  # type: ignore[attr-defined]
        tools.call("get_market_regime")  # recorder restored after the block
        assert len(sink) == 2


class TestAnalysisAgent:
    def test_analyze_returns_structured_analysis(self) -> None:
        result = AnalysisAgent(_tools()).analyze("FPT")
        assert result.symbol == "FPT"
        assert 0.0 <= result.overall_score <= 100.0
        assert 0.0 <= result.confidence <= 1.0
        assert result.thesis
        assert result.catalysts and result.risks and result.invalidation_conditions
        assert result.market_regime in ("BULL", "BEAR", "SIDEWAYS", "VOLATILE")
        assert result.evidence, "RAG evidence must back the analysis (§19)"

    def test_warnings_are_honest(self) -> None:
        joined = " ".join(AnalysisAgent(_tools()).analyze("FPT").warnings)
        assert "Corporate-events" in joined
        assert "T014" not in joined

    def test_deterministic(self) -> None:
        agent = AnalysisAgent(_tools())
        assert agent.analyze("VCB").model_dump() == agent.analyze("VCB").model_dump()

    def test_unknown_symbol_raises(self) -> None:
        with pytest.raises(ValueError, match="NOPE"):
            AnalysisAgent(_tools()).analyze("NOPE")

    def test_confidence_blend(self) -> None:
        strong = AnalysisAgent._confidence(
            signal="POSITIVE",
            data_quality=95.0,
            evidence_count=4,
            regime_compat=0.9,
            ranking_conf=0.8,
        )
        weak = AnalysisAgent._confidence(
            signal="NEUTRAL",
            data_quality=40.0,
            evidence_count=0,
            regime_compat=0.3,
            ranking_conf=0.1,
        )
        assert 0.0 <= weak < strong <= 1.0
        assert abs(sum(CONFIDENCE_WEIGHTS.values()) - 1.0) < 1e-9

    def test_peer_avg_helper(self) -> None:
        assert AnalysisAgent._peer_avg({"average_score": 61.234}) == 61.23
        assert AnalysisAgent._peer_avg({"average_score": None}) is None

    def test_invalidations_include_top_factor_and_regime(self) -> None:
        joined = " ".join(
            AnalysisAgent._invalidations(
                {"regime": "BULL"}, {"max_drawdown": -0.12}, "momentum"
            )
        )
        assert "momentum" in joined
        assert "BULL" in joined


class TestResearchAgent:
    def test_brief_structure(self) -> None:
        brief = ResearchAgent(_tools()).research("FPT")
        assert brief.symbol == "FPT"
        assert brief.profile["company_name"]
        assert brief.key_facts
        assert brief.evidence
        assert 0.0 <= brief.confidence <= 1.0
        assert any("Corporate-events" in w for w in brief.warnings)

    def test_query_flows_into_evidence(self) -> None:
        brief = ResearchAgent(_tools()).research("VCB", query="VCB tín dụng bán lẻ")
        assert brief.evidence[0]["claim"] == "VCB tín dụng bán lẻ"

    def test_unknown_symbol_raises(self) -> None:
        with pytest.raises(ValueError, match="NOPE"):
            ResearchAgent(_tools()).research("NOPE")

    def test_confidence_without_evidence(self) -> None:
        assert ResearchAgent._confidence([]) == 0.0
        assert ResearchAgent._confidence([{"confidence": 0.5}]) == 0.5


class TestMonitoringAgent:
    def test_watchlist_alerts(self) -> None:
        alerts = MonitoringAgent(_tools()).monitor(["FPT", "VCB"])
        assert alerts
        assert {a.severity for a in alerts} <= {
            SEVERITY_NORMAL,
            SEVERITY_WARNING,
            SEVERITY_CRITICAL,
        }
        assert any(a.alert_type == ALERT_RISK_INCREASED for a in alerts)
        assert all(a.symbol in ("FPT", "VCB") for a in alerts)

    def test_signal_change_detection(self) -> None:
        tools = _tools()
        agent = MonitoringAgent(tools)
        current = str(tools.call("get_ranking", symbol="FPT")["signal"])
        previous = "NEUTRAL" if current != "NEUTRAL" else "POSITIVE"
        alerts = agent.monitor(["FPT"], previous_signals={"FPT": previous})
        changes = [a for a in alerts if a.alert_type == ALERT_SIGNAL_CHANGED]
        assert changes, "a different previous signal must raise an alert"
        assert changes[0].payload["previous_signal"] == previous

    def test_polarity_flip_is_critical_and_soft_change_is_warning(self) -> None:
        agent = MonitoringAgent(_tools())
        flip = agent._signal_alerts(  # noqa: SLF001
            "FPT", {"signal": "NEGATIVE", "overall_score": 36.8}, {"FPT": "POSITIVE"}
        )
        assert flip and flip[0].severity == SEVERITY_CRITICAL
        soft = agent._signal_alerts(  # noqa: SLF001
            "FPT", {"signal": "NEUTRAL", "overall_score": 42.0}, {"FPT": "POSITIVE"}
        )
        assert soft and soft[0].severity == SEVERITY_WARNING
        assert agent._signal_alerts("FPT", {"signal": "NEUTRAL"}, {}) == []  # noqa: SLF001

    def test_state_remembers_previous_signal(self) -> None:
        agent = MonitoringAgent(_tools())
        agent.monitor(["FPT"])
        assert "FPT" in agent._last_signals  # noqa: SLF001
        second = agent.monitor(["FPT"])
        assert not [a for a in second if a.alert_type == ALERT_SIGNAL_CHANGED]
        agent.reset()
        assert agent._last_signals == {}  # noqa: SLF001

    def test_breakout_and_rsi_thresholds(self) -> None:
        alerts = MonitoringAgent._technical_alerts(
            "FPT",
            {
                "price": 120.0,
                "high_20": 119.0,
                "low_20": 100.0,
                "volume": 300,
                "volume_avg_20": 100.0,
            },
            {"series": {"rsi14": 78.5}},
        )
        assert ALERT_TECHNICAL_BREAKOUT in {a.alert_type for a in alerts}
        rsi_alert = next(a for a in alerts if "rsi14" in a.payload)
        assert rsi_alert.severity == SEVERITY_WARNING
        oversold = MonitoringAgent._technical_alerts(
            "FPT",
            {"price": 101.0, "high_20": 130.0, "low_20": 100.0},
            {"series": {"rsi14": 22.0}},
        )
        assert any("oversold" in a.message for a in oversold)
        quiet = MonitoringAgent._technical_alerts(
            "FPT",
            {"price": 110.0, "high_20": 130.0, "low_20": 100.0, "volume": 100,
             "volume_avg_20": 100.0},
            {"series": {"rsi14": 55.0}},
        )
        assert quiet == []

    def test_news_keyword_alert(self) -> None:
        alerts = MonitoringAgent._news_alerts(
            "FPT",
            {
                "news": [{"title": "FPT bị xử phạt vi phạm", "source": "cafef"}],
                "count": 1,
            },
        )
        assert alerts and alerts[0].alert_type == ALERT_IMPORTANT_NEWS
        assert alerts[0].payload["headlines"] == ["FPT bị xử phạt vi phạm"]
        assert MonitoringAgent._news_alerts("FPT", {"news": [], "count": 0}) == []

    def test_quality_gate_alerts(self) -> None:
        critical = MonitoringAgent._quality_alerts(
            "FPT", {"available": True, "overall_score": 92.0, "below_threshold": True}
        )
        assert critical and critical[0].severity == SEVERITY_CRITICAL
        warning = MonitoringAgent._quality_alerts(
            "FPT", {"available": True, "overall_score": 65.0, "below_threshold": False}
        )
        assert warning and warning[0].severity == SEVERITY_WARNING
        assert (
            MonitoringAgent._quality_alerts(
                "FPT",
                {"available": True, "overall_score": 90.0, "below_threshold": False},
            )
            == []
        )
        assert MonitoringAgent._quality_alerts("FPT", {"available": False}) == []

    def test_unknown_symbol_raises(self) -> None:
        with pytest.raises(ValueError, match="NOPE"):
            MonitoringAgent(_tools()).monitor(["NOPE"])


class TestPortfolioAgent:
    def _positions(self) -> list[PortfolioPosition]:
        return [
            PortfolioPosition(symbol="FPT", quantity=1000),
            PortfolioPosition(symbol="VCB", quantity=500),
        ]

    def test_snapshot_math(self) -> None:
        tools = _tools()
        snapshot = PortfolioAgent(tools).analyze(self._positions())
        fpt = tools.call("get_stock_price", symbol="FPT")["price"]
        vcb = tools.call("get_stock_price", symbol="VCB")["price"]
        assert snapshot.total_value == pytest.approx(1000 * fpt + 500 * vcb, rel=1e-6)
        assert snapshot.positions == 2
        assert 0.0 < snapshot.top_concentration_pct <= 100.0
        assert 0.0 < snapshot.max_sector_pct <= 100.0
        assert 0 <= snapshot.avg_score <= 100.0
        assert snapshot.risk_budget_used_pct > 0
        assert snapshot.warnings

    def test_concentration_alert(self) -> None:
        snapshot = PortfolioAgent(_tools()).analyze(
            [
                PortfolioPosition(symbol="FPT", quantity=10_000),
                PortfolioPosition(symbol="VCB", quantity=10),
            ]
        )
        assert snapshot.top_concentration_pct > 50.0
        alerts = {a.alert_type: a for a in snapshot.alerts}
        assert alerts["concentration"].severity == SEVERITY_CRITICAL

    def test_sector_exposure_alert(self) -> None:
        snapshot = PortfolioAgent(_tools()).analyze(
            [
                PortfolioPosition(symbol="VCB", quantity=1000),
                PortfolioPosition(symbol="BID", quantity=1000),
                PortfolioPosition(symbol="TCB", quantity=1000),
            ]
        )
        assert snapshot.max_sector_pct > 90.0
        assert any(a.alert_type == "sector_exposure" for a in snapshot.alerts)
        assert "Correlation" in " ".join(snapshot.warnings)

    def test_single_position_warning(self) -> None:
        snapshot = PortfolioAgent(_tools()).analyze(
            [PortfolioPosition(symbol="FPT", quantity=100)]
        )
        assert snapshot.positions == 1
        assert any("Single-position" in w for w in snapshot.warnings)

    def test_empty_portfolio_raises(self) -> None:
        with pytest.raises(ValueError, match="no market value"):
            PortfolioAgent(_tools()).analyze([])

    def test_unknown_symbol_raises(self) -> None:
        with pytest.raises(ValueError, match="NOPE"):
            PortfolioAgent(_tools()).analyze([PortfolioPosition(symbol="NOPE", quantity=1)])

    def test_risk_budget_scale(self) -> None:
        agent = PortfolioAgent(_tools())
        tight = agent.analyze(self._positions(), risk_budget_annual_vol=0.01)
        loose = agent.analyze(self._positions(), risk_budget_annual_vol=1.0)
        assert tight.risk_budget_used_pct > loose.risk_budget_used_pct
        assert any(a.alert_type == "risk_budget" for a in tight.alerts)


class TestRegistry:
    def test_default_registry(self) -> None:
        registry = build_default_registry()
        assert registry.tasks() == ["analyze", "monitor", "portfolio", "research"]
        payload = {row["agent_id"]: row for row in registry.to_payload()}
        assert payload["analysis"]["output_schema"] == "InvestmentAnalysis"
        assert payload["monitoring"]["output_schema"] == "MonitoringReport"
        assert payload["portfolio"]["output_schema"] == "PortfolioRiskSnapshot"
        assert payload["research"]["output_schema"] == "ResearchBrief"
        assert all(row["status"] == "active" for row in payload.values())
        assert "get_stock_price" in payload["analysis"]["available_tools"]

    def test_registry_unknown_task(self) -> None:
        with pytest.raises(ValueError, match="unknown agent task"):
            build_default_registry().get("nope")

    def test_custom_registration(self) -> None:
        registry = AgentRegistry()
        registry.register(
            AgentSpec(
                agent_id="custom",
                version="0.1",
                system_prompt_version="custom-v1",
                output_schema="InvestmentAnalysis",
                task="custom",
                plan=("step",),
                available_tools=("get_stock_price",),
            )
        )
        assert registry.tasks() == ["custom"]
        assert registry.get("custom").to_payload()["plan"] == ["step"]


class TestAuditTrail:
    def _run(self, status: str = "succeeded") -> AgentRunRecord:
        run = AgentRunRecord(
            user_request="Phân tích FPT",
            agent_id="analysis",
            agent_version="1.0",
            model=MODEL,
            status=status,
            final_output={"symbol": "FPT", "confidence": 0.5},
        )
        return run

    def test_record_get_list(self) -> None:
        trail = AuditTrail()
        run = self._run()
        trail.record(run)
        assert len(trail) == 1
        assert trail.get(run.agent_run_id) is run
        assert trail.list_runs()[0] is run
        assert trail.list_runs(agent_id="research") == []

    def test_latest_analysis_only_for_success(self) -> None:
        trail = AuditTrail()
        run = self._run()
        trail.record(run)
        assert trail.latest_analysis("fpt") is run
        assert trail.latest_analysis("VCB") is None

    def test_max_records_trimming(self) -> None:
        trail = AuditTrail(max_records=2)
        runs = [self._run() for _ in range(3)]
        for run in runs:
            trail.record(run)
        assert len(trail) == 2
        assert trail.get(runs[0].agent_run_id) is None
        assert trail.get(runs[2].agent_run_id) is runs[2]

    def test_clear(self) -> None:
        trail = AuditTrail()
        trail.record(self._run())
        trail.clear()
        assert len(trail) == 0


class TestOrchestrator:
    def test_analyze_run_is_audited(self) -> None:
        orchestrator = _orchestrator()
        run = orchestrator.analyze("FPT")
        assert run.status == "succeeded"
        assert run.agent_id == "analysis"
        assert run.model == MODEL
        assert run.prompt_version == "analysis-prompt-v1"
        assert run.plan == orchestrator.plan_for(TASK_ANALYZE)
        assert len(run.tools_called) == 12
        assert run.attempts == 1
        assert run.latency_ms >= 0
        assert run.finished_at is not None
        assert run.final_output is not None
        assert run.final_output["symbol"] == "FPT"
        assert len(orchestrator.audit) == 1
        assert orchestrator.audit.get(run.agent_run_id) is run

    def test_run_mirrors_tool_calls(self) -> None:
        run = _orchestrator().analyze("VCB")
        names = [call.tool_name for call in run.tools_called]
        assert names[0] == "get_market_regime"
        assert "get_ranking" in names
        assert "search_evidence" in names
        evidence_call = next(c for c in run.tools_called if c.tool_name == "search_evidence")
        assert "query" in evidence_call.tool_input
        assert evidence_call.tool_output["count"] >= 1

    def test_failed_run_is_recorded_not_raised(self) -> None:
        orchestrator = _orchestrator()
        run = orchestrator.analyze("NOPE")
        assert run.status == "failed"
        assert run.final_output is not None
        assert "unknown symbol" in run.final_output["error"]
        assert orchestrator.audit.get(run.agent_run_id) is run

    def test_unknown_task_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown agent task"):
            _orchestrator().run("nope", {})

    def test_research_monitor_portfolio_runs(self) -> None:
        orchestrator = _orchestrator()
        research = orchestrator.research("FPT", query="FPT profile")
        assert research.status == "succeeded"
        assert research.agent_id == "research"
        monitor = orchestrator.monitor(["FPT", "VCB"])
        assert monitor.status == "succeeded"
        assert monitor.final_output is not None
        assert isinstance(monitor.final_output["symbols"], list)
        assert monitor.final_output["critical"] + monitor.final_output["normal"] >= 1
        portfolio = orchestrator.portfolio(
            [PortfolioPosition(symbol="FPT", quantity=100)]
        )
        assert portfolio.status == "succeeded"
        assert portfolio.final_output is not None
        assert portfolio.final_output["positions"] == 1

    def test_audit_history_and_latest(self) -> None:
        orchestrator = _orchestrator()
        orchestrator.analyze("FPT")
        orchestrator.research("FPT")
        assert [r.agent_id for r in orchestrator.audit.list_runs()] == [
            "research",
            "analysis",
        ]
        assert [r.agent_id for r in orchestrator.audit.list_runs(agent_id="analysis")] == [
            "analysis"
        ]
        assert orchestrator.audit.latest_analysis("fpt") is not None

    def test_submit_and_execute_deferred(self) -> None:
        orchestrator = _orchestrator()
        queued = orchestrator.submit(TASK_ANALYZE, {"symbol": "FPT"})
        assert queued.status == "queued"
        assert orchestrator.audit.get(queued.agent_run_id) is queued
        finished = orchestrator.execute_deferred(queued.agent_run_id)
        assert finished.status == "succeeded"
        with pytest.raises(ValueError, match="unknown queued agent run"):
            orchestrator.execute_deferred(queued.agent_run_id)

    def test_retry_until_success(self) -> None:
        orchestrator = _orchestrator(max_attempts=3, timeout_s=None)
        attempts = {"count": 0}

        def flaky(params: object) -> InvestmentAnalysis:
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RuntimeError("transient tool failure")
            return _analysis()

        orchestrator._handlers[TASK_ANALYZE] = flaky  # noqa: SLF001
        run = orchestrator.run(TASK_ANALYZE, {"symbol": "FPT"})
        assert run.status == "succeeded"
        assert run.attempts == 2

    def test_retry_exhausted_reports_failure(self) -> None:
        orchestrator = _orchestrator(max_attempts=2, timeout_s=None)

        def broken(params: object) -> InvestmentAnalysis:
            raise RuntimeError("permanent failure")

        orchestrator._handlers[TASK_ANALYZE] = broken  # noqa: SLF001
        run = orchestrator.run(TASK_ANALYZE, {"symbol": "FPT"})
        assert run.status == "failed"
        assert run.attempts == 2
        assert "permanent failure" in str(run.final_output)

    def test_timeout_is_reported(self) -> None:
        orchestrator = _orchestrator(max_attempts=1, timeout_s=0.01)

        def slow(params: object) -> InvestmentAnalysis:
            time.sleep(0.2)
            return _analysis()

        orchestrator._handlers[TASK_ANALYZE] = slow  # noqa: SLF001
        run = orchestrator.run(TASK_ANALYZE, {"symbol": "FPT"})
        assert run.status == "timeout"
        assert "AgentTimeoutError" in str(run.final_output)

    def test_registry_and_plan_exposed(self) -> None:
        orchestrator = _orchestrator()
        assert orchestrator.registry.tasks() == ["analyze", "monitor", "portfolio", "research"]
        assert orchestrator.plan_for("monitor")[0] == "Price & volume"
        assert "get_risk" in orchestrator.tools.catalog


class TestWorkerAgentCli:
    def test_parse_positions(self) -> None:
        from apps.worker.cli import _parse_positions

        assert _parse_positions("FPT:100, vcb:250") == [
            {"symbol": "FPT", "quantity": 100.0},
            {"symbol": "VCB", "quantity": 250.0},
        ]
        with pytest.raises(ValueError, match="invalid position"):
            _parse_positions("FPT")
        with pytest.raises(ValueError, match="--positions is required"):
            _parse_positions("")

    def test_run_agent_analyze(self, capsys: pytest.CaptureFixture[str]) -> None:
        from apps.worker.cli import main

        assert main(["run-agent", "--task", "analyze", "--symbol", "FPT"]) == 0
        assert '"agent_id": "analysis"' in capsys.readouterr().out

    def test_run_agent_requires_symbol(self) -> None:
        from apps.worker.cli import main

        with pytest.raises(ValueError, match="--symbol is required"):
            main(["run-agent", "--task", "analyze"])

    def test_run_agent_portfolio(self, capsys: pytest.CaptureFixture[str]) -> None:
        from apps.worker.cli import main

        assert main(["run-agent", "--task", "portfolio", "--positions", "FPT:100"]) == 0
        assert '"positions": 1' in capsys.readouterr().out
