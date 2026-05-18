"""Tests for model_scout — free-model discovery and profile ranking."""

from __future__ import annotations

from earn_money.agent.model_scout import (
    ModelInfo,
    is_free_model,
    parse_models_response,
    score_model,
)
from earn_money.agent.task_router import TaskType

# ---------------------------------------------------------------------------
# is_free_model
# ---------------------------------------------------------------------------


def test_is_free_model_free_suffix() -> None:
    assert is_free_model({"id": "qwen/qwen3-235b:free", "pricing": {}})


def test_is_free_model_zero_pricing() -> None:
    raw = {"id": "some/model", "pricing": {"prompt": "0", "completion": "0"}}
    assert is_free_model(raw)


def test_is_free_model_paid() -> None:
    raw = {"id": "some/model", "pricing": {"prompt": "0.001", "completion": "0.002"}}
    assert not is_free_model(raw)


def test_is_free_model_missing_pricing_is_not_free() -> None:
    assert not is_free_model({"id": "some/model"})


def test_is_free_model_partial_zero_is_not_free() -> None:
    # Only prompt free, completion paid → not free
    raw = {"id": "some/model", "pricing": {"prompt": "0", "completion": "0.001"}}
    assert not is_free_model(raw)


# ---------------------------------------------------------------------------
# parse_models_response
# ---------------------------------------------------------------------------

_SAMPLE_RESPONSE = {
    "data": [
        {
            "id": "qwen/qwen3-coder:free",
            "name": "Qwen3 Coder (free)",
            "context_length": 32768,
            "pricing": {"prompt": "0", "completion": "0"},
        },
        {
            "id": "openai/gpt-4o",
            "name": "GPT-4o",
            "context_length": 128000,
            "pricing": {"prompt": "0.005", "completion": "0.015"},
        },
        {
            "id": "deepseek/deepseek-r1:free",
            "name": "DeepSeek R1 (free)",
            "context_length": 65536,
            "pricing": {"prompt": "0", "completion": "0"},
        },
    ]
}


def test_parse_models_response_filters_paid() -> None:
    models = parse_models_response(_SAMPLE_RESPONSE)
    ids = [m.id for m in models]
    assert "openai/gpt-4o" not in ids


def test_parse_models_response_keeps_free() -> None:
    models = parse_models_response(_SAMPLE_RESPONSE)
    assert len(models) == 2


def test_parse_models_response_captures_context_length() -> None:
    models = parse_models_response(_SAMPLE_RESPONSE)
    by_id = {m.id: m for m in models}
    assert by_id["deepseek/deepseek-r1:free"].context_length == 65536


def test_parse_models_response_empty_data() -> None:
    assert parse_models_response({"data": []}) == []


def test_parse_models_response_missing_data_key() -> None:
    assert parse_models_response({}) == []


# ---------------------------------------------------------------------------
# score_model
# ---------------------------------------------------------------------------

_CODER = ModelInfo(id="qwen/qwen3-coder:free", name="Qwen3 Coder", context_length=32768)
_REASONER = ModelInfo(id="deepseek/deepseek-r1:free", name="DeepSeek R1", context_length=65536)
_GRANITE = ModelInfo(id="ibm/granite-3b-code:free", name="Granite 3B", context_length=8192)
_MISTRAL = ModelInfo(id="mistralai/mistral-small:free", name="Mistral Small", context_length=32768)
_GENERIC = ModelInfo(id="meta-llama/llama-3.1-8b:free", name="Llama 3.1 8B", context_length=16384)


def test_score_coding_security_prefers_coder() -> None:
    assert score_model(_CODER, TaskType.CODING_SECURITY) > score_model(
        _GENERIC, TaskType.CODING_SECURITY
    )


def test_score_deep_reasoning_prefers_r1() -> None:
    assert score_model(_REASONER, TaskType.DEEP_REASONING) > score_model(
        _CODER, TaskType.DEEP_REASONING
    )


def test_score_structured_extraction_prefers_granite() -> None:
    assert score_model(_GRANITE, TaskType.STRUCTURED_EXTRACTION) > score_model(
        _GENERIC, TaskType.STRUCTURED_EXTRACTION
    )


def test_score_report_writing_prefers_mistral() -> None:
    assert score_model(_MISTRAL, TaskType.REPORT_WRITING) > score_model(
        _GRANITE, TaskType.REPORT_WRITING
    )


def test_score_context_length_bonus() -> None:
    small = ModelInfo(id="some/model:free", name="Small", context_length=4096)
    large = ModelInfo(id="some/model:free", name="Large", context_length=131072)
    # Large context should score higher (all else equal)
    assert score_model(large, TaskType.DEFAULT_ASSISTANT) > score_model(
        small, TaskType.DEFAULT_ASSISTANT
    )


def test_score_unknown_task_type_returns_zero_for_no_keywords() -> None:
    # score_model should not crash on any TaskType
    model = ModelInfo(id="xyz/unknown:free", name="Unknown", context_length=0)
    for task in TaskType:
        assert isinstance(score_model(model, task), int)


