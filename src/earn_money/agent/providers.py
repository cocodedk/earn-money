"""LLM provider abstraction for the agent decider.

A `Provider` exposes one method — `complete(system, user)` → string.
Concrete adapters wrap each vendor's SDK behind that interface so
the decider can swap providers without touching its logic.

Selection at runtime:

    EARN_MONEY_LLM_PROVIDER=anthropic|openai|openrouter|huggingface
    EARN_MONEY_LLM_MODEL=<model-name>          # provider-specific default if unset

API keys come from env: ANTHROPIC_API_KEY, OPENAI_API_KEY,
OPENROUTER_API_KEY, HF_API_KEY.
"""

from __future__ import annotations

import os
from typing import Protocol

# Provider-default models. Override via EARN_MONEY_LLM_MODEL.
_DEFAULT_ANTHROPIC = "claude-opus-4-7"
_DEFAULT_OPENAI = "gpt-4o-mini"
_DEFAULT_OPENROUTER = "openrouter/auto"
_DEFAULT_HUGGINGFACE = "meta-llama/Meta-Llama-3.1-70B-Instruct"
_MAX_TOKENS = 4096


class Provider(Protocol):
    """Minimal LLM interface — system + user → reply text."""

    def complete(self, *, system: str, user: str) -> str: ...


class ProviderUnavailable(Exception):
    """Raised when the requested provider's SDK or API key is missing."""


class AnthropicProvider:
    def __init__(self, model: str | None = None) -> None:
        try:
            import anthropic
        except ImportError as exc:
            raise ProviderUnavailable("install with [agent-anthropic]") from exc
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise ProviderUnavailable("ANTHROPIC_API_KEY unset")
        self._client = anthropic.Anthropic()
        self._model = model or _DEFAULT_ANTHROPIC

    def complete(self, *, system: str, user: str) -> str:
        resp = self._client.messages.create(
            model=self._model, max_tokens=_MAX_TOKENS,
            system=system, messages=[{"role": "user", "content": user}],
        )
        return _extract_anthropic_text(resp)


class OpenAIProvider:
    """Works for both api.openai.com and any OpenAI-compatible endpoint.
    OpenRouter and many self-hosted gateways speak the same dialect."""

    def __init__(
        self, model: str | None = None, *,
        api_key_env: str = "OPENAI_API_KEY", base_url: str | None = None,
        default_model: str = _DEFAULT_OPENAI,
    ) -> None:
        try:
            import openai
        except ImportError as exc:
            raise ProviderUnavailable("install with [agent-openai]") from exc
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise ProviderUnavailable(f"{api_key_env} unset")
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self._model = model or default_model

    def complete(self, *, system: str, user: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model, max_tokens=_MAX_TOKENS,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return (resp.choices[0].message.content or "").strip()


class HuggingFaceProvider:
    """Talks to the HF Inference API via raw HTTP (no extra SDK)."""

    def __init__(self, model: str | None = None) -> None:
        api_key = os.environ.get("HF_API_KEY")
        if not api_key:
            raise ProviderUnavailable("HF_API_KEY unset")
        import httpx
        self._client = httpx.Client(
            base_url="https://api-inference.huggingface.co",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )
        self._model = model or _DEFAULT_HUGGINGFACE

    def complete(self, *, system: str, user: str) -> str:
        prompt = f"[SYSTEM]\n{system}\n\n[USER]\n{user}\n\n[ASSISTANT]\n"
        resp = self._client.post(
            f"/models/{self._model}",
            json={"inputs": prompt, "parameters": {"max_new_tokens": _MAX_TOKENS}},
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data:
            return str(data[0].get("generated_text", "")).strip()
        return ""


def from_env() -> Provider:
    """Pick a provider from `EARN_MONEY_LLM_PROVIDER` + optional model."""
    name = (os.environ.get("EARN_MONEY_LLM_PROVIDER") or "anthropic").lower()
    model = os.environ.get("EARN_MONEY_LLM_MODEL") or None
    if name == "anthropic":
        return AnthropicProvider(model=model)
    if name == "openai":
        return OpenAIProvider(model=model)
    if name == "openrouter":
        return OpenAIProvider(
            model=model, api_key_env="OPENROUTER_API_KEY",
            base_url="https://openrouter.ai/api/v1",
            default_model=_DEFAULT_OPENROUTER,
        )
    if name == "huggingface":
        return HuggingFaceProvider(model=model)
    raise ProviderUnavailable(f"unknown provider {name!r}")


def _extract_anthropic_text(resp: object) -> str:
    """Defensive: the anthropic SDK returns a list of content blocks. Pull
    the first text block; tolerate missing/unexpected shapes."""
    content = getattr(resp, "content", None) or []
    for block in content:
        if getattr(block, "type", None) == "text":
            return str(getattr(block, "text", "")).strip()
    return ""
