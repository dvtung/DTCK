"""Phase-5 tests — LLM provider abstraction and agent reasoning wiring.

Covers ADR-005 (one provider-agnostic interface) and §4/§47 (the LLM only
*reasons over* deterministic quant output — it never computes the numbers).

Everything here is offline: the Ollama adapter is exercised through
``httpx.MockTransport``, and the Analysis Agent through a fake client, so the
suite never needs a running Ollama server.
"""

from __future__ import annotations

import json

import httpx
import pytest

from apps.api.services.agent_service import get_llm_client, get_orchestrator
from apps.api.services.market_data import MarketService
from src.agents.analysis.agent import AnalysisAgent
from src.agents.llm.client import (
    LLMClient,
    MockLLMClient,
    OllamaLLMClient,
    create_llm_client,
)
from src.agents.orchestrator.agent import MODEL, Orchestrator
from src.agents.tools import ToolCatalog
from src.rag.service import RagService

OLLAMA_URL = "http://ollama.test:11434"


class _FakeLLM:
    """Deterministic stand-in for a real provider (records the prompt)."""

    model = "fake-llm"

    def __init__(self, text: str = "Luận điểm từ LLM.", *, error: Exception | None = None) -> None:
        self.text = text
        self.error = error
        self.calls: list[dict[str, object]] = []

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> str:
        self.calls.append(
            {
                "prompt": prompt,
                "system": system,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if self.error is not None:
            raise self.error
        return self.text


def _tools() -> ToolCatalog:
    """Tool catalog over deterministic in-memory services (as in test_agents)."""
    market = MarketService()
    rag = RagService()
    rag.ingest_news_items(market.list_news())
    return ToolCatalog(market, rag)


# --------------------------------------------------------------- factory
class TestFactory:
    def test_mock_provider_returns_mock_client(self) -> None:
        client = create_llm_client("mock")
        assert isinstance(client, MockLLMClient)
        assert client.generate("bất kỳ") == ""

    def test_provider_name_is_case_insensitive(self) -> None:
        assert isinstance(create_llm_client("MOCK"), MockLLMClient)

    def test_local_provider_returns_ollama_client(self) -> None:
        client = create_llm_client(
            "local", model="qwen3.5", base_url=OLLAMA_URL, timeout_seconds=12.0
        )
        assert isinstance(client, OllamaLLMClient)
        assert client.base_url == OLLAMA_URL
        assert client.model == "qwen3.5"
        assert client.timeout_seconds == 12.0

    def test_ollama_alias_is_accepted(self) -> None:
        assert isinstance(create_llm_client("ollama"), OllamaLLMClient)

    def test_unknown_provider_falls_back_to_mock(self) -> None:
        assert isinstance(create_llm_client("definitely-not-a-provider"), MockLLMClient)

    def test_clients_satisfy_the_protocol(self) -> None:
        assert isinstance(MockLLMClient(), LLMClient)
        assert isinstance(OllamaLLMClient(), LLMClient)


# ------------------------------------------------------------ ollama adapter
class TestOllamaAdapter:
    @staticmethod
    def _client(handler, captured: list[httpx.Request] | None = None) -> OllamaLLMClient:
        def _handler(request: httpx.Request) -> httpx.Response:
            if captured is not None:
                captured.append(request)
            return handler(request)

        return OllamaLLMClient(
            base_url=OLLAMA_URL,
            model="qwen3.5",
            transport=httpx.MockTransport(_handler),
        )

    def test_generate_posts_the_documented_payload(self) -> None:
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"response": "  FPT tích cực.  "})

        text = self._client(handler, captured).generate(
            "phân tích FPT", system="bạn là chuyên gia", temperature=0.2, max_tokens=256
        )

        assert text == "FPT tích cực."  # trimmed
        assert len(captured) == 1
        request = captured[0]
        assert request.method == "POST"
        assert str(request.url) == f"{OLLAMA_URL}/api/generate"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["model"] == "qwen3.5"
        assert payload["prompt"] == "phân tích FPT"
        assert payload["stream"] is False
        assert payload["system"] == "bạn là chuyên gia"
        assert payload["options"] == {"temperature": 0.2, "num_predict": 256}

    def test_system_is_omitted_when_absent(self) -> None:
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"response": "ok"})

        self._client(handler, captured).generate("chỉ prompt")
        assert "system" not in json.loads(captured[0].content.decode("utf-8"))

    def test_think_block_is_disabled_by_default(self) -> None:
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"response": "ok"})

        self._client(handler, captured).generate("x")
        assert json.loads(captured[0].content.decode("utf-8"))["think"] is False

    def test_think_field_can_be_omitted_for_older_servers(self) -> None:
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"response": "ok"})

        client = self._client(handler, captured)
        with_think_disabled = OllamaLLMClient(
            base_url=OLLAMA_URL, model="m", transport=client._transport, think=None
        )
        with_think_disabled.generate("x")
        assert "think" not in json.loads(captured[0].content.decode("utf-8"))

    def test_missing_response_field_yields_empty_string(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"done": True})

        assert self._client(handler).generate("x") == ""

    def test_http_error_propagates_to_the_caller(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"error": "model not found"})

        with pytest.raises(httpx.HTTPStatusError):
            self._client(handler).generate("x")

    def test_timeout_propagates_to_the_caller(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("ollama too slow", request=request)

        with pytest.raises(httpx.ReadTimeout):
            self._client(handler).generate("x")


# ------------------------------------------------- analysis agent wiring
class TestAnalysisAgentLLM:
    def test_thesis_uses_llm_text_when_available(self) -> None:
        fake = _FakeLLM("FPT dẫn dắt nhờ động lực công nghệ và định giá hợp lý.")
        result = AnalysisAgent(_tools(), llm=fake).analyze("FPT")

        assert result.thesis == "FPT dẫn dắt nhờ động lực công nghệ và định giá hợp lý."
        assert len(fake.calls) == 1
        prompt = str(fake.calls[0]["prompt"])
        # The prompt carries the quant facts, so the model cannot invent numbers.
        assert "FPT" in prompt and "Overall Score" in prompt
        assert fake.calls[0]["temperature"] == 0.2

    def test_quant_output_is_untouched_by_the_llm(self) -> None:
        baseline = AnalysisAgent(_tools()).analyze("FPT")
        enriched = AnalysisAgent(_tools(), llm=_FakeLLM("bất kỳ")).analyze("FPT")

        assert baseline.overall_score == enriched.overall_score
        assert baseline.technical_score == enriched.technical_score
        assert baseline.evidence == enriched.evidence
        assert baseline.catalysts == enriched.catalysts
        assert baseline.risks == enriched.risks
        assert baseline.confidence == enriched.confidence
        assert baseline.thesis != enriched.thesis

    def test_failure_falls_back_to_the_deterministic_thesis(self) -> None:
        fake = _FakeLLM(error=RuntimeError("ollama unreachable"))
        result = AnalysisAgent(_tools(), llm=fake).analyze("FPT")

        assert "scores" in result.thesis  # template thesis kept
        assert len(fake.calls) == 1  # attempted exactly once
        assert result.overall_score > 0

    def test_blank_llm_answer_falls_back_to_the_template(self) -> None:
        result = AnalysisAgent(_tools(), llm=_FakeLLM("   ")).analyze("FPT")
        assert "scores" in result.thesis

    def test_no_llm_means_deterministic_output(self) -> None:
        agent = AnalysisAgent(_tools())
        assert agent.analyze("VCB").model_dump() == agent.analyze("VCB").model_dump()


# ------------------------------------------------------- orchestrator audit
class TestOrchestratorLLM:
    def test_model_label_stays_baseline_without_llm(self) -> None:
        orchestrator = Orchestrator(_tools())
        assert orchestrator.llm is None
        assert orchestrator.model == MODEL
        assert orchestrator.analyze("FPT").model == MODEL

    def test_model_label_records_the_llm_when_enabled(self) -> None:
        orchestrator = Orchestrator(
            _tools(), llm=create_llm_client("local", model="qwen3.5", base_url=OLLAMA_URL)
        )
        assert orchestrator.model == f"{MODEL}+qwen3.5"
        assert orchestrator.analyze("FPT").model == f"{MODEL}+qwen3.5"
        # Registry/metadata contract is unchanged; only the audit label varies.
        assert orchestrator.registry.get("analyze").agent_id == "analysis"


# --------------------------------------------------------- service wiring
class TestAgentServiceWiring:
    def test_mock_provider_builds_no_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from apps.api.config import settings

        monkeypatch.setattr(settings, "llm_provider", "mock")
        get_llm_client.cache_clear()
        get_orchestrator.cache_clear()
        try:
            assert get_llm_client() is None
            assert get_orchestrator().llm is None
            assert get_orchestrator().model == MODEL
        finally:
            get_llm_client.cache_clear()
            get_orchestrator.cache_clear()

    def test_local_provider_builds_the_ollama_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from apps.api.config import settings

        monkeypatch.setattr(settings, "llm_provider", "local")
        monkeypatch.setattr(settings, "llm_model", "qwen3.5")
        monkeypatch.setattr(settings, "llm_base_url", OLLAMA_URL)
        monkeypatch.setattr(settings, "llm_timeout_seconds", 90)
        get_llm_client.cache_clear()
        get_orchestrator.cache_clear()
        try:
            client = get_llm_client()
            assert isinstance(client, OllamaLLMClient)
            assert client is not None and client.model == "qwen3.5"
            assert client.base_url == OLLAMA_URL
            orchestrator = get_orchestrator()
            assert orchestrator.llm is client
            # Run budget must clear the client timeout (§45) or every run times out.
            assert orchestrator._timeout_s is not None
            assert orchestrator._timeout_s > 90.0
        finally:
            get_llm_client.cache_clear()
            get_orchestrator.cache_clear()
