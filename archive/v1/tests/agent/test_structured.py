"""Tests for the structured-output request helper."""

from __future__ import annotations

import json
from typing import Any

import pytest

from earn_money.agent.providers import Provider
from earn_money.agent.schemas import (
    SCANNER_ANALYSIS_SCHEMA,
    parse_scanner_analysis,
)
from earn_money.agent.structured import (
    StructuredOutputError,
    request_structured,
)


class _ScriptedProvider:
    """Returns replies from a queue and records every call."""

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.calls: list[dict[str, Any]] = []

    def complete(
        self, *, system: str, user: str,
        task: Any = None,
        response_format: dict[str, object] | None = None,
    ) -> str:
        self.calls.append(
            {"system": system, "user": user, "task": task,
             "response_format": response_format}
        )
        return self._replies.pop(0) if self._replies else "{}"


_SAMPLE_SCHEMA: dict[str, Any] = {
    "name": "demo",
    "schema": {
        "type": "object",
        "required": ["answer"],
        "properties": {"answer": {"type": "string"}},
    },
}


def test_passes_response_format_to_provider() -> None:
    stub = _ScriptedProvider(['{"answer": "yes"}'])
    provider: Provider = stub  # type: ignore[assignment]
    out = request_structured(
        provider, system="system", user="user", schema=_SAMPLE_SCHEMA,
    )
    assert out == {"answer": "yes"}
    rf = stub.calls[0]["response_format"]
    assert isinstance(rf, dict)
    assert rf["type"] == "json_schema"
    assert rf["json_schema"] == _SAMPLE_SCHEMA


def test_augments_system_prompt_with_schema() -> None:
    stub = _ScriptedProvider(['{"answer": "yes"}'])
    provider: Provider = stub  # type: ignore[assignment]
    request_structured(
        provider, system="original system", user="x",
        schema=_SAMPLE_SCHEMA,
    )
    augmented = stub.calls[0]["system"]
    assert "original system" in augmented
    assert "matches the schema" in augmented
    assert "answer" in augmented  # schema body inlined


def test_validator_runs_and_passes_on_valid_payload() -> None:
    payload = {
        "finding_title": "X", "affected_asset": "a.example.com",
        "evidence_ids": [], "severity": "low", "confidence": "high",
        "reasoning_summary": "r", "remediation": "fix",
        "injection_suspected": False, "injection_indicators": [],
        "ignored_untrusted_instructions": [],
        "requires_human_review": False, "proposed_actions": [],
    }
    stub = _ScriptedProvider([json.dumps(payload)])
    provider: Provider = stub  # type: ignore[assignment]
    out = request_structured(
        provider, system="s", user="u",
        schema=SCANNER_ANALYSIS_SCHEMA,
        validator=lambda p: parse_scanner_analysis(p),
    )
    assert out["finding_title"] == "X"


def test_repair_retry_on_invalid_first_reply() -> None:
    """First reply is invalid JSON; helper retries once and succeeds."""
    valid = {"answer": "second time lucky"}
    stub = _ScriptedProvider(["definitely not json", json.dumps(valid)])
    provider: Provider = stub  # type: ignore[assignment]
    out = request_structured(
        provider, system="s", user="u", schema=_SAMPLE_SCHEMA,
    )
    assert out == valid
    assert len(stub.calls) == 2
    # The retry user prompt mentions the previous error.
    retry_prompt = stub.calls[1]["user"]
    assert "previous reply failed" in retry_prompt


def test_retry_cap_raises_after_one_attempt() -> None:
    """Two bad replies in a row → StructuredOutputError."""
    stub = _ScriptedProvider(["nope", "also nope"])
    provider: Provider = stub  # type: ignore[assignment]
    with pytest.raises(StructuredOutputError):
        request_structured(
            provider, system="s", user="u", schema=_SAMPLE_SCHEMA,
        )
    assert len(stub.calls) == 2


def test_validator_failure_triggers_repair_retry() -> None:
    """Valid JSON but failing validator → repair attempt, then succeed."""
    bad = {"answer": 42}  # validator wants string
    good = {"answer": "string"}

    def validator(payload: dict[str, Any]) -> None:
        if not isinstance(payload.get("answer"), str):
            raise ValueError("answer must be a string")

    stub = _ScriptedProvider([json.dumps(bad), json.dumps(good)])
    provider: Provider = stub  # type: ignore[assignment]
    out = request_structured(
        provider, system="s", user="u", schema=_SAMPLE_SCHEMA,
        validator=validator,
    )
    assert out == good


def test_falls_back_when_provider_rejects_response_format() -> None:
    """Spec §5: when the provider doesn't accept response_format, the
    helper falls back to the JSON-only prompt path and still works."""
    seen_kwargs: list[dict[str, Any]] = []

    class _NoResponseFormat:
        def complete(self, *, system: str, user: str, task: Any = None) -> str:
            seen_kwargs.append({"system": system, "user": user, "task": task})
            return '{"answer": "fallback worked"}'

    provider: Provider = _NoResponseFormat()  # type: ignore[assignment]
    out = request_structured(
        provider, system="s", user="u", schema=_SAMPLE_SCHEMA,
    )
    assert out == {"answer": "fallback worked"}
    # System prompt is still augmented with the schema body.
    assert "answer" in seen_kwargs[0]["system"]


def test_task_kwarg_threads_through() -> None:
    """Task type goes to the provider so OpenRouter can route by profile."""
    stub = _ScriptedProvider(['{"answer": "ok"}'])
    provider: Provider = stub  # type: ignore[assignment]
    request_structured(
        provider, system="s", user="u", schema=_SAMPLE_SCHEMA,
        task="structured_extraction",
    )
    assert stub.calls[0]["task"] == "structured_extraction"
