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


class OpenRouterProvider(LLMProvider):
    """Calls OpenRouter's OpenAI-compatible API."""

    def __init__(
        self, model: str, api_key: str, extra_params: dict | None = None,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._extra_params = extra_params or {}
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                api_key=self._api_key,
                base_url="https://openrouter.ai/api/v1",
            )
        return self._client

    async def complete(
        self,
        system_prompt: str,
        messages: list[dict],
    ) -> LLMResponse:
        client = self._get_client()
        all_messages = [{"role": "system", "content": system_prompt}, *messages]
        kwargs: dict = {
            "model": self._model,
            "messages": all_messages,
            "max_tokens": 4096,
        }
        if self._extra_params:
            kwargs["extra_body"] = self._extra_params
        response = await client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        usage = response.usage
        return LLMResponse(
            raw_text=choice.message.content or "",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            model=self._model,
        )


def create_provider(
    model: str,
    api_key: str = "",
    provider_type: str = "anthropic",
    extra_params: dict | None = None,
) -> LLMProvider:
    """Factory: return a provider instance by type name."""
    if provider_type == "mock":
        return MockProvider(model=model)
    if provider_type == "anthropic":
        return AnthropicProvider(model=model, api_key=api_key)
    if provider_type == "openrouter":
        return OpenRouterProvider(
            model=model, api_key=api_key, extra_params=extra_params,
        )
    raise ValueError(f"Unknown provider_type {provider_type!r}")
