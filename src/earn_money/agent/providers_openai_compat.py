"""OpenAI-compatible provider adapter — used for OpenAI, OpenRouter,
and any self-hosted gateway that speaks the same dialect.

Kept in its own module so the parent `providers.py` stays under the
200-line cap and the vendor-specific bits cluster cleanly.
"""

from __future__ import annotations

import contextlib
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
_MAX_TOKENS_DEFAULT = 4096


def openrouter_max_tokens() -> int:
    """Per-request max output tokens. Override via OPENROUTER_MAX_TOKENS
    to fit the key's per-call credit budget on OpenRouter (HTTP 402 is
    raised pre-flight when `max_tokens * price` exceeds available credit).

    Read per-call so operators can flip the env var without redeploying.
    Default: 4096. Invalid or non-positive values fall back to default.
    """
    raw = os.environ.get("OPENROUTER_MAX_TOKENS")
    if raw is None:
        return _MAX_TOKENS_DEFAULT
    try:
        value = int(raw)
    except ValueError:
        return _MAX_TOKENS_DEFAULT
    return value if value > 0 else _MAX_TOKENS_DEFAULT


class ProviderUnavailable(Exception):
    """Raised when the requested provider's SDK or API key is missing."""


class ProviderError(Exception):
    """Raised when the provider call fails or returns garbage.

    `status_code` carries the HTTP status when the underlying failure was
    an API response (e.g. 400/401/402/429). None for non-HTTP errors
    (timeouts, transport, decode). Callers use it to gate retry policy.
    """

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


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
        self, *, system: str, user: str,
        task: str | TaskType | None = None,
        response_format: dict[str, object] | None = None,
    ) -> str:
        kwargs: dict[str, Any] = {
            "model": self._resolve(task),
            "max_tokens": openrouter_max_tokens(),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if response_format is not None:
            kwargs["response_format"] = response_format
        try:
            resp = self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            # Surface enough detail to actually diagnose. The openai SDK
            # wraps HTTP failures as APIStatusError with a `.status_code`
            # and `.response` we can read; for anything else fall back
            # to str(exc) so the message at least reaches the journal.
            status = getattr(exc, "status_code", None)
            body = ""
            response = getattr(exc, "response", None)
            if response is not None:
                with contextlib.suppress(Exception):
                    body = response.text[:500]
            detail = f"{type(exc).__name__}"
            if status is not None:
                detail += f" status={status}"
            msg = str(exc)
            if msg:
                detail += f" msg={msg[:200]}"
            if body:
                detail += f" body={body!r}"
            raise ProviderError(
                f"openai-compatible call failed: {detail}",
                status_code=status,
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
