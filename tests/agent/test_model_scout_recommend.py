"""Tests for model_scout recommend_profiles and fetch_models_json."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from earn_money.agent.model_scout import ModelInfo, recommend_profiles
from earn_money.agent.task_router import TaskType, profile_env_var

_CODER = ModelInfo(id="qwen/qwen3-coder:free", name="Qwen3 Coder", context_length=32768)
_REASONER = ModelInfo(id="deepseek/deepseek-r1:free", name="DeepSeek R1", context_length=65536)
_GRANITE = ModelInfo(id="ibm/granite-3b-code:free", name="Granite 3B", context_length=8192)
_MISTRAL = ModelInfo(id="mistralai/mistral-small:free", name="Mistral Small", context_length=32768)
_GENERIC = ModelInfo(id="meta-llama/llama-3.1-8b:free", name="Llama 3.1 8B", context_length=16384)

# ---------------------------------------------------------------------------
# recommend_profiles
# ---------------------------------------------------------------------------


def test_recommend_profiles_covers_all_task_types() -> None:
    models = [_CODER, _REASONER, _GRANITE, _MISTRAL, _GENERIC]
    result = recommend_profiles(models)
    for task in TaskType:
        assert profile_env_var(task) in result


def test_recommend_profiles_sets_global_default() -> None:
    result = recommend_profiles([_GENERIC])
    assert "OPENROUTER_DEFAULT_MODEL" in result


def test_recommend_profiles_empty_returns_empty() -> None:
    assert recommend_profiles([]) == {}


def test_recommend_profiles_picks_highest_scorer() -> None:
    # For DEEP_REASONING, _REASONER should win over _GENERIC
    result = recommend_profiles([_GENERIC, _REASONER])
    assert result[profile_env_var(TaskType.DEEP_REASONING)] == _REASONER.id


# ---------------------------------------------------------------------------
# fetch_models_json (mocked HTTP)
# ---------------------------------------------------------------------------


def test_fetch_models_json_calls_correct_url() -> None:
    from earn_money.agent.model_scout_fetch import fetch_models_json

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": []}
    mock_resp.raise_for_status = MagicMock()

    with patch("earn_money.agent.model_scout_fetch.httpx.Client") as mock_client_cls:
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.get.return_value = mock_resp
        mock_client_cls.return_value = mock_ctx

        result = fetch_models_json("sk-test", "https://openrouter.ai/api/v1")

    mock_ctx.get.assert_called_once_with("https://openrouter.ai/api/v1/models")
    assert result == {"data": []}


def test_fetch_models_json_passes_auth_header() -> None:
    from earn_money.agent.model_scout_fetch import fetch_models_json

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": []}
    mock_resp.raise_for_status = MagicMock()

    with patch("earn_money.agent.model_scout_fetch.httpx.Client") as mock_client_cls:
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.get.return_value = mock_resp
        mock_client_cls.return_value = mock_ctx

        fetch_models_json("sk-testkey")

    call_kwargs = mock_client_cls.call_args.kwargs
    assert call_kwargs["headers"]["Authorization"] == "Bearer sk-testkey"
