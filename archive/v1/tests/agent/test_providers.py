"""Tests for the LLM provider adapters — env-driven selection, OpenRouter
headers/timeout, task router integration, error translation."""

from __future__ import annotations

import pytest

from earn_money.agent.providers import (
    AnthropicProvider,
    HuggingFaceProvider,
    OpenAIProvider,
    ProviderUnavailable,
    from_env,
)
from earn_money.agent.providers_openai_compat import (
    ProviderError,
    openrouter_headers,
    openrouter_max_tokens,
    openrouter_timeout,
)


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "EARN_MONEY_LLM_PROVIDER",
        "EARN_MONEY_LLM_MODEL",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "OPENROUTER_BASE_URL",
        "OPENROUTER_SITE_URL",
        "OPENROUTER_APP_NAME",
        "OPENROUTER_TIMEOUT_SECONDS",
        "OPENROUTER_MAX_TOKENS",
        "OPENROUTER_DEFAULT_MODEL",
        "OPENROUTER_MODEL_CODING_SECURITY",
        "HF_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)


def test_from_env_default_is_anthropic_requires_key() -> None:
    with pytest.raises(ProviderUnavailable):
        from_env()


def test_from_env_anthropic_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    provider = from_env()
    assert isinstance(provider, AnthropicProvider)


def test_from_env_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EARN_MONEY_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    provider = from_env()
    assert isinstance(provider, OpenAIProvider)


def test_from_env_openrouter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EARN_MONEY_LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    provider = from_env()
    # OpenRouter uses the same SDK as OpenAI under the hood.
    assert isinstance(provider, OpenAIProvider)


def test_from_env_huggingface(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EARN_MONEY_LLM_PROVIDER", "huggingface")
    monkeypatch.setenv("HF_API_KEY", "hf-test")
    provider = from_env()
    assert isinstance(provider, HuggingFaceProvider)


def test_from_env_unknown_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EARN_MONEY_LLM_PROVIDER", "totally-fake")
    with pytest.raises(ProviderUnavailable):
        from_env()


def test_openrouter_headers_empty_by_default() -> None:
    assert openrouter_headers() == {}


def test_openrouter_headers_with_site_and_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_SITE_URL", "https://cocode.dk")
    monkeypatch.setenv("OPENROUTER_APP_NAME", "earn-money")
    headers = openrouter_headers()
    assert headers == {
        "HTTP-Referer": "https://cocode.dk",
        "X-Title": "earn-money",
    }


def test_openrouter_timeout_default() -> None:
    assert openrouter_timeout() == 60.0


def test_openrouter_timeout_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_TIMEOUT_SECONDS", "30")
    assert openrouter_timeout() == 30.0


def test_openrouter_timeout_invalid_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_TIMEOUT_SECONDS", "not a number")
    assert openrouter_timeout() == 60.0


def test_openrouter_timeout_negative_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_TIMEOUT_SECONDS", "-5")
    assert openrouter_timeout() == 60.0


def test_openrouter_max_tokens_default() -> None:
    assert openrouter_max_tokens() == 4096


def test_openrouter_max_tokens_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Operator drops the per-call budget without redeploying when the
    OpenRouter key runs low on credit (HTTP 402 fires on max_tokens * price)."""
    monkeypatch.setenv("OPENROUTER_MAX_TOKENS", "2000")
    assert openrouter_max_tokens() == 2000


def test_openrouter_max_tokens_invalid_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_MAX_TOKENS", "not a number")
    assert openrouter_max_tokens() == 4096


def test_openrouter_max_tokens_zero_or_negative_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_MAX_TOKENS", "0")
    assert openrouter_max_tokens() == 4096
    monkeypatch.setenv("OPENROUTER_MAX_TOKENS", "-1")
    assert openrouter_max_tokens() == 4096


def test_provider_error_default_status_code_is_none() -> None:
    err = ProviderError("boom")
    assert err.status_code is None


def test_provider_error_carries_status_code() -> None:
    """Callers gate retry policy on the HTTP status. 402 (credit exhausted)
    and 401/403 (auth) must be distinguishable from 400 (bad request)."""
    err = ProviderError("402 out of credit", status_code=402)
    assert err.status_code == 402


def test_openai_provider_resolves_via_task_router_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenRouter mode: per-call `task` picks from profile env vars."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setenv("OPENROUTER_MODEL_CODING_SECURITY", "qwen/qwen3-coder")
    provider = OpenAIProvider(
        api_key_env="OPENROUTER_API_KEY",
        use_task_router=True,
    )
    # Direct unit-test the resolution (no real API call).
    assert provider._resolve("coding_security") == "qwen/qwen3-coder"


def test_openai_provider_constructor_model_wins_over_router(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setenv("OPENROUTER_MODEL_CODING_SECURITY", "qwen/qwen3-coder")
    provider = OpenAIProvider(
        model="explicit-override",
        api_key_env="OPENROUTER_API_KEY",
        use_task_router=True,
    )
    assert provider._resolve("coding_security") == "explicit-override"


def test_openai_provider_router_unconfigured_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec §4: if a task-specific model is missing, fall back to the
    static default rather than crashing."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    provider = OpenAIProvider(
        api_key_env="OPENROUTER_API_KEY",
        use_task_router=True,
        default_model="static-fallback",
    )
    assert provider._resolve("report_writing") == "static-fallback"
