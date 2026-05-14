"""Tests for the task router — env-driven model selection."""

from __future__ import annotations

import pytest

from earn_money.agent.task_router import (
    RouterUnconfigured,
    TaskType,
    coerce_task,
    resolve_model,
)


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear every router-related env var before each test."""
    for var in (
        "OPENROUTER_DEFAULT_MODEL",
        "OPENROUTER_MODEL_DEFAULT_ASSISTANT",
        "OPENROUTER_MODEL_CODING_SECURITY",
        "OPENROUTER_MODEL_REPORT_WRITING",
        "OPENROUTER_MODEL_STRUCTURED_EXTRACTION",
        "OPENROUTER_MODEL_DEEP_REASONING",
    ):
        monkeypatch.delenv(var, raising=False)


def test_coerce_task_none_returns_default() -> None:
    assert coerce_task(None) is TaskType.DEFAULT_ASSISTANT


def test_coerce_task_passes_through_known_string() -> None:
    assert coerce_task("coding_security") is TaskType.CODING_SECURITY


def test_coerce_task_unknown_string_falls_back_to_default() -> None:
    """Spec §4: unknown task types fall back to default_assistant."""
    assert coerce_task("totally_unknown") is TaskType.DEFAULT_ASSISTANT


def test_coerce_task_passes_through_enum() -> None:
    assert coerce_task(TaskType.DEEP_REASONING) is TaskType.DEEP_REASONING


def test_resolve_model_uses_profile_specific_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_MODEL_CODING_SECURITY", "qwen/qwen3-coder")
    assert resolve_model("coding_security") == "qwen/qwen3-coder"


def test_resolve_model_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Profile env unset but global default set → use the global."""
    monkeypatch.setenv("OPENROUTER_DEFAULT_MODEL", "qwen/qwen3-235b-a22b")
    assert resolve_model("report_writing") == "qwen/qwen3-235b-a22b"


def test_resolve_model_raises_when_nothing_configured() -> None:
    with pytest.raises(RouterUnconfigured):
        resolve_model("structured_extraction")


def test_resolve_model_none_uses_default_task_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_MODEL_DEFAULT_ASSISTANT", "mistralai/mistral-small")
    assert resolve_model(None) == "mistralai/mistral-small"


def test_resolve_model_unknown_task_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_MODEL_DEFAULT_ASSISTANT", "mistralai/mistral-small")
    assert resolve_model("not_a_real_task") == "mistralai/mistral-small"


def test_resolve_model_profile_specific_wins_over_global(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_DEFAULT_MODEL", "global-default")
    monkeypatch.setenv("OPENROUTER_MODEL_DEEP_REASONING", "deepseek/deepseek-r1")
    assert resolve_model("deep_reasoning") == "deepseek/deepseek-r1"
