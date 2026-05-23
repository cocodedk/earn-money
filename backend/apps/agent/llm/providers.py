from __future__ import annotations

import abc
import json
from dataclasses import dataclass


@dataclass
class LLMResponse:
    raw_text: str
    input_tokens: int
    output_tokens: int
    model: str


class LLMProvider(abc.ABC):
    """Abstract base for LLM completion providers."""

    @abc.abstractmethod
    async def complete(
        self,
        system_prompt: str,
        messages: list[dict],
    ) -> LLMResponse:
        """Return an LLMResponse for the given prompt and messages."""


_MOCK_ACTION = json.dumps({
    "action": "observe_page",
    "goal": "Understand the current page layout",
    "reason": "Need baseline before proceeding",
    "hypothesis": "Page is reachable and renders HTML",
    "include_screenshot": False,
})


class MockProvider(LLMProvider):
    """Returns a fixed observe_page action for use in unit tests."""

    def __init__(self, model: str = "mock") -> None:
        self._model = model

    async def complete(
        self,
        system_prompt: str,
        messages: list[dict],
    ) -> LLMResponse:
        return LLMResponse(
            raw_text=_MOCK_ACTION,
            input_tokens=len(system_prompt) // 4,
            output_tokens=len(_MOCK_ACTION) // 4,
            model=self._model,
        )


class AnthropicProvider(LLMProvider):
    """Calls the Anthropic Messages API via the anthropic SDK."""

    def __init__(self, model: str, api_key: str) -> None:
        self._model = model
        self._api_key = api_key
        self._client = None  # created lazily

    def _get_client(self):
        if self._client is None:
            import anthropic  # lazy import — not required at module load
            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
        return self._client

    async def complete(
        self,
        system_prompt: str,
        messages: list[dict],
    ) -> LLMResponse:
        client = self._get_client()
        response = await client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
        )
        raw_text = response.content[0].text
        return LLMResponse(
            raw_text=raw_text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=self._model,
        )


def create_provider(
    model: str,
    api_key: str = "",
    provider_type: str = "anthropic",
) -> LLMProvider:
    """Factory: return a provider instance by type name."""
    if provider_type == "mock":
        return MockProvider(model=model)
    if provider_type == "anthropic":
        return AnthropicProvider(model=model, api_key=api_key)
    raise ValueError(f"Unknown provider_type {provider_type!r}")
