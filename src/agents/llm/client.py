"""LLM provider abstraction for DTCK agents (ADR-005).

Provides a unified interface for generating text syntheses (e.g. investment
theses) across Mock, Local (Ollama/vLLM), OpenAI, and Anthropic backends.
Deterministic quant calculations always remain strictly outside the LLM (§4, §47).
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

import httpx

logger = logging.getLogger(__name__)


@runtime_checkable
class LLMClient(Protocol):
    """Provider abstraction for LLM text generation (ADR-005)."""

    #: Model label recorded in the agent audit trail (§13.2 ``agent_runs.model``).
    model: str

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> str:
        """Synchronously generate text response from the provider."""
        ...


class MockLLMClient:
    """Mock provider for unit tests and offline zero-cost execution."""

    model = "mock"

    def __init__(self, default_response: str = "") -> None:
        self.default_response = default_response

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> str:
        return self.default_response


class OllamaLLMClient:
    """Adapter for local Ollama server via REST API.

    Mirrors the provider convention used by ``src.data.providers`` (an optional
    ``transport`` makes the client unit-testable with ``httpx.MockTransport``).
    """

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "qwen2.5-7b-65k:latest",
        timeout_seconds: float = 45.0,
        transport: Any | None = None,
        think: bool | None = False,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._transport = transport
        #: ``False`` disables the reasoning block on hybrid models (Qwen3.5 …):
        #: the answer alone is what the agent needs, and thinking tokens would
        #: otherwise blow the §45 latency budget (§47). ``None`` omits the field
        #: for servers that predate it; non-thinking models ignore it.
        self.think = think

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=self.timeout_seconds, transport=self._transport)

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system:
            payload["system"] = system
        if self.think is not None:
            payload["think"] = self.think

        with self._client() as client:
            response = client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
        return str(data.get("response", "")).strip()


def create_llm_client(
    provider: str = "mock",
    *,
    model: str = "qwen2.5-7b-65k:latest",
    base_url: str | None = None,
    timeout_seconds: float = 45.0,
    api_key: str | None = None,
    think: bool | None = False,
) -> LLMClient:
    """Factory creating an LLMClient instance according to ADR-005."""
    norm_provider = (provider or "mock").strip().lower()
    if norm_provider in {"mock", "none", ""}:
        return MockLLMClient()
    if norm_provider in {"local", "ollama"}:
        target_url = base_url or "http://127.0.0.1:11434"
        return OllamaLLMClient(
            base_url=target_url,
            model=model or "qwen2.5-7b-65k:latest",
            timeout_seconds=timeout_seconds,
            think=think,
        )
    # Extensible for "openai" / "anthropic" in a later phase (ADR-005).
    logger.info("Unsupported or deferred provider '%s'; falling back to mock", norm_provider)
    return MockLLMClient()
