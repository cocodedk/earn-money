"""OpenAI-compatible provider adapter — used for OpenAI, OpenRouter,
and any self-hosted gateway that speaks the same dialect.

Kept in its own module so the parent `providers.py` stays under the
200-line cap and the vendor-specific bits cluster cleanly.
"""

from __future__ import annotations

import os
from typing import Any

from earn_money.agent.task_router import (
    RouterUnconfigured,
    TaskType,
    resolve_model,
)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_OPENROUTER_TIMEOUT_DEFAULT = 60.0
_DEFAULT_OPENAI = "gpt-4o-mini"
_MAX_TOKENS = 4096


class ProviderUnavailable(Exception):
    """Raised when the requested provider's SDK or API key is missing."""


class ProviderError(Exception):
    """Raised when the provider call fails or returns garbage."""


class OpenAIProvider:
    """Talks to any OpenAI-compatible endpoint.

    For OpenAI proper: leave `base_url` unset.
    For OpenRouter: pass `base_url=OPENROUTER_BASE_URL`, `api_key_env=
    "OPENROUTER_API_KEY"`, plus the optional `extra_headers`. Also set
    `use_task_router=True` so per-call `task` kwargs resolve via the
    model-profile env vars (spec §3/§4).
    """

    def __init__(
        self, model: str | None = None, *,
        api_key_env: str = "OPENAI_API_KEY",
        base_url: str | None = None,
        default_model: str = _DEFAULT_OPENAI,
        extra_headers: dict[str, str] | None = None,
        timeout: float | None = None,
        use_task_router: bool = False,
    ) -> None:
        try:
            import openai
        except ImportError as exc:
            raise ProviderUnavailable("install with [agent-openai]") from exc
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise ProviderUnavailable(f"{api_key_env} unset")
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        if extra_headers:
            kwargs["default_headers"] = extra_headers
        if timeout is not None:
            kwargs["timeout"] = timeout
        self._client = openai.OpenAI(**kwargs)
        self._configured_model = model
        self._default_model = default_model
        self._use_task_router = use_task_router

    def _resolve(self, task: str | TaskType | None) -> str:
        """Pick the model: explicit constructor wins, else task router
        (when enabled), else the static default."""
        if self._configured_model:
            return self._configured_model
        if self._use_task_router:
            try:
                return resolve_model(task)
            except RouterUnconfigured:
                pass
        return self._default_model

    def complete(
        self, *, system: str, user: str, task: str | TaskType | None = None,
    ) -> str:
        try:
            resp = self._client.chat.completions.create(
                model=self._resolve(task), max_tokens=_MAX_TOKENS,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except Exception as exc:
            raise ProviderError(
                f"openai-compatible call failed: {type(exc).__name__}"
            ) from exc
        return (resp.choices[0].message.content or "").strip()


def openrouter_headers() -> dict[str, str]:
    """Optional HTTP-Referer + X-Title per OpenRouter docs."""
    out: dict[str, str] = {}
    site = os.environ.get("OPENROUTER_SITE_URL")
    if site:
        out["HTTP-Referer"] = site
    app = os.environ.get("OPENROUTER_APP_NAME")
    if app:
        out["X-Title"] = app
    return out


def openrouter_timeout() -> float:
    raw = os.environ.get("OPENROUTER_TIMEOUT_SECONDS")
    if raw is None:
        return _OPENROUTER_TIMEOUT_DEFAULT
    try:
        value = float(raw)
    except ValueError:
        return _OPENROUTER_TIMEOUT_DEFAULT
    return value if value > 0 else _OPENROUTER_TIMEOUT_DEFAULT
