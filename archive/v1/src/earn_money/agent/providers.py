"""LLM provider abstraction for the agent decider.

A `Provider` exposes one method — `complete(system, user, task)` —
returning the model's reply text. Concrete adapters wrap each vendor's
SDK behind that interface so the decider can swap providers without
touching its logic.

Selection at runtime:

    EARN_MONEY_LLM_PROVIDER=anthropic|openai|openrouter|huggingface

OpenRouter additionally honours the task router (spec §3 + §4) so a
per-call `task` kwarg picks the right model from the profile env vars.
Per-vendor env vars carry the API key + optional headers:

    OPENROUTER_BASE_URL (default https://openrouter.ai/api/v1)
    OPENROUTER_SITE_URL    → HTTP-Referer
    OPENROUTER_APP_NAME    → X-Title
    OPENROUTER_TIMEOUT_SECONDS
"""

from __future__ import annotations

import os
from typing import Protocol

from earn_money.agent.providers_openai_compat import (
    OPENROUTER_BASE_URL,
    OpenAIProvider,
    ProviderError,
    ProviderUnavailable,
    openrouter_headers,
    openrouter_timeout,
)
from earn_money.agent.task_router import TaskType

_DEFAULT_ANTHROPIC = "claude-opus-4-7"
_DEFAULT_HUGGINGFACE = "meta-llama/Meta-Llama-3.1-70B-Instruct"
_MAX_TOKENS = 4096

__all__ = [
    "AnthropicProvider",
    "HuggingFaceProvider",
    "OpenAIProvider",
    "Provider",
    "ProviderError",
    "ProviderUnavailable",
    "from_env",
]


class Provider(Protocol):
    """Minimal LLM interface — system + user (+ optional task +
    response_format) → reply text."""

    def complete(
        self, *, system: str, user: str,
        task: str | TaskType | None = None,
        response_format: dict[str, object] | None = None,
    ) -> str: ...


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

    def complete(
        self, *, system: str, user: str,
        task: str | TaskType | None = None,
        response_format: dict[str, object] | None = None,
    ) -> str:
        # Anthropic model is fixed at constructor time. `task` and
        # `response_format` are accepted for protocol parity but
        # ignored — Anthropic uses tools for structured output, which
        # the structured.py JSON-only fallback handles via the
        # augmented system prompt.
        resp = self._client.messages.create(
            model=self._model, max_tokens=_MAX_TOKENS,
            system=system, messages=[{"role": "user", "content": user}],
        )
        return _extract_anthropic_text(resp)


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

    def complete(
        self, *, system: str, user: str,
        task: str | TaskType | None = None,
        response_format: dict[str, object] | None = None,
    ) -> str:
        # HF Inference API doesn't speak OpenAI's response_format; the
        # caller (structured.py) augments the system prompt instead.
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
            model=model,
            api_key_env="OPENROUTER_API_KEY",
            base_url=os.environ.get("OPENROUTER_BASE_URL") or OPENROUTER_BASE_URL,
            extra_headers=openrouter_headers(),
            timeout=openrouter_timeout(),
            use_task_router=True,
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
