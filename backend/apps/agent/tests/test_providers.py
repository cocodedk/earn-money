from __future__ import annotations

import asyncio
import json
import pytest
from apps.agent.llm.providers import (
    LLMResponse,
    LLMProvider,
    MockProvider,
    AnthropicProvider,
    OpenRouterProvider,
    create_provider,
)


def run(coro):
    return asyncio.run(coro)


_SYSTEM = "You are a security testing agent."
_MESSAGES = [{"role": "user", "content": "What do you see?"}]


class TestLLMResponse:
    def test_fields(self):
        r = LLMResponse(
            raw_text="hello",
            input_tokens=10,
            output_tokens=5,
            model="mock",
        )
        assert r.raw_text == "hello"
        assert r.input_tokens == 10
        assert r.output_tokens == 5
        assert r.model == "mock"


class TestMockProvider:
    def test_is_llm_provider(self):
        assert isinstance(MockProvider(), LLMProvider)

    def test_returns_llm_response(self):
        result = run(MockProvider().complete(_SYSTEM, _MESSAGES))
        assert isinstance(result, LLMResponse)

    def test_raw_text_is_valid_json(self):
        result = run(MockProvider().complete(_SYSTEM, _MESSAGES))
        parsed = json.loads(result.raw_text)
        assert isinstance(parsed, dict)

    def test_raw_text_is_observe_page_action(self):
        result = run(MockProvider().complete(_SYSTEM, _MESSAGES))
        parsed = json.loads(result.raw_text)
        assert parsed["action"] == "observe_page"

    def test_model_name_propagates(self):
        result = run(MockProvider(model="test-model").complete(_SYSTEM, _MESSAGES))
        assert result.model == "test-model"

    def test_token_counts_positive(self):
        result = run(MockProvider().complete(_SYSTEM, _MESSAGES))
        assert result.input_tokens >= 0
        assert result.output_tokens >= 0

    def test_ignores_messages_content(self):
        result1 = run(MockProvider().complete(_SYSTEM, _MESSAGES))
        result2 = run(MockProvider().complete(_SYSTEM, []))
        assert result1.raw_text == result2.raw_text


class TestAnthropicProvider:
    def test_is_llm_provider(self):
        assert isinstance(AnthropicProvider("claude-sonnet-4-5", "key"), LLMProvider)

    def test_model_stored(self):
        p = AnthropicProvider("claude-sonnet-4-5", "key")
        assert p._model == "claude-sonnet-4-5"

    def test_client_is_lazy(self):
        p = AnthropicProvider("claude-sonnet-4-5", "key")
        assert p._client is None


class TestOpenRouterProvider:
    def test_is_llm_provider(self):
        assert isinstance(OpenRouterProvider("anthropic/claude-sonnet-4-6", "key"), LLMProvider)

    def test_model_stored(self):
        p = OpenRouterProvider("anthropic/claude-sonnet-4-6", "key")
        assert p._model == "anthropic/claude-sonnet-4-6"

    def test_client_is_lazy(self):
        p = OpenRouterProvider("anthropic/claude-sonnet-4-6", "key")
        assert p._client is None

    def test_deepseek_model_stored(self):
        p = OpenRouterProvider("deepseek/deepseek-v4-pro", "key")
        assert p._model == "deepseek/deepseek-v4-pro"

    def test_extra_params_stored(self):
        extra = {"reasoning": {"effort": "high"}}
        p = OpenRouterProvider("deepseek/deepseek-v4-pro", "key", extra_params=extra)
        assert p._extra_params == extra

    def test_extra_params_default_empty(self):
        p = OpenRouterProvider("deepseek/deepseek-v4-pro", "key")
        assert p._extra_params == {}


class TestCreateProvider:
    def test_mock_type(self):
        p = create_provider("mock-model", provider_type="mock")
        assert isinstance(p, MockProvider)

    def test_anthropic_type(self):
        p = create_provider("claude-sonnet-4-5", api_key="k", provider_type="anthropic")
        assert isinstance(p, AnthropicProvider)

    def test_openrouter_type(self):
        p = create_provider("anthropic/claude-sonnet-4-6", api_key="k", provider_type="openrouter")
        assert isinstance(p, OpenRouterProvider)

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown provider_type"):
            create_provider("x", provider_type="unknown")

    def test_default_is_anthropic(self):
        p = create_provider("claude-sonnet-4-5", api_key="k")
        assert isinstance(p, AnthropicProvider)

    def test_openrouter_with_extra_params(self):
        extra = {"reasoning": {"effort": "high"}}
        p = create_provider(
            "deepseek/deepseek-v4-pro", api_key="k",
            provider_type="openrouter", extra_params=extra,
        )
        assert isinstance(p, OpenRouterProvider)
        assert p._extra_params == extra
        assert p._model == "deepseek/deepseek-v4-pro"


class TestBuildProviderFromPolicy:
    """Tests for tasks._build_provider reading model_policy dicts."""

    def test_mock_provider_for_mock_policy(self):
        from apps.agent.tasks import _build_provider
        p = _build_provider({"provider": "mock"})
        assert isinstance(p, MockProvider)

    def test_openrouter_reads_model_and_reasoning(self):
        from apps.agent.tasks import _build_provider
        import os
        os.environ["OPENROUTER_API_KEY"] = "test-key"
        try:
            p = _build_provider({
                "provider": "openrouter",
                "model": "deepseek/deepseek-v4-pro",
                "reasoning": {"effort": "high"},
            })
            assert isinstance(p, OpenRouterProvider)
            assert p._model == "deepseek/deepseek-v4-pro"
            assert p._extra_params["reasoning"] == {"effort": "high"}
        finally:
            del os.environ["OPENROUTER_API_KEY"]

    def test_anthropic_reads_api_key_from_env(self):
        from apps.agent.tasks import _build_provider
        import os
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        try:
            p = _build_provider({
                "provider": "anthropic",
                "model": "claude-sonnet-4-5",
            })
            assert isinstance(p, AnthropicProvider)
            assert p._model == "claude-sonnet-4-5"
        finally:
            del os.environ["ANTHROPIC_API_KEY"]
