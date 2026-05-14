"""Tests for the per-action-type allowlist."""

from __future__ import annotations

import pytest

from earn_money.agent.action_allowlist import (
    any_requires_human_review,
    validate_action,
    validate_actions,
)


@pytest.mark.parametrize("action_type", [
    "classify_finding",
    "draft_remediation",
    "map_finding_to_control",
    "extract_technology_hint",
    "summarize_evidence",
    "suggest_passive_check",
    "produce_report_text",
    "produce_structured_json",
])
def test_low_risk_actions_allowed_no_review(action_type: str) -> None:
    v = validate_action(action_type)
    assert v.allowed is True
    assert v.risk_level == "low"
    assert v.requires_human_review is False
    assert v.reason == "ok"


@pytest.mark.parametrize("action_type", [
    "severity_downgrade",
    "propose_new_runner",
    "propose_one_off_script",
])
def test_medium_risk_actions_allowed_with_human_review(action_type: str) -> None:
    v = validate_action(action_type)
    assert v.allowed is True
    assert v.risk_level == "medium"
    assert v.requires_human_review is True


@pytest.mark.parametrize("action_type", [
    "active_exploitation",
    "credential_use",
    "destructive_payload",
    "data_exfiltration",
    "send_message",
    "modify_scope",
    "modify_scanner_config",
    "call_arbitrary_url",
    "shell_command",
    "authenticated_request",
    "delete_finding",
    "suppress_finding",
    "hide_finding",
])
def test_high_risk_actions_blocked(action_type: str) -> None:
    v = validate_action(action_type)
    assert v.allowed is False
    assert v.risk_level == "high"
    assert v.requires_human_review is True
    assert "blocked" in v.reason or "allowlist" in v.reason


def test_unknown_action_blocked_with_human_review() -> None:
    v = validate_action("call_home_with_fries")
    assert v.allowed is False
    assert v.risk_level == "high"
    assert v.requires_human_review is True
    assert "unknown" in v.reason.lower()


def test_validate_actions_parallel_list() -> None:
    proposed = [
        {"action_type": "classify_finding", "risk_level": "low"},
        {"action_type": "shell_command", "risk_level": "low"},  # model lies
        {"action_type": "made_up"},
    ]
    results = validate_actions(proposed)
    assert len(results) == 3
    assert results[0].allowed is True
    # Even though the model claimed `risk_level="low"`, the allowlist
    # is the source of truth — high-risk + blocked.
    assert results[1].allowed is False
    assert results[1].risk_level == "high"
    assert results[2].allowed is False


def test_any_requires_human_review_aggregates() -> None:
    results = validate_actions([{"action_type": "classify_finding"}])
    assert any_requires_human_review(results) is False
    results = validate_actions([
        {"action_type": "classify_finding"},
        {"action_type": "severity_downgrade"},
    ])
    assert any_requires_human_review(results) is True


def test_validate_actions_caps_at_twenty() -> None:
    proposed = [{"action_type": "classify_finding"}] * 50
    results = validate_actions(proposed)
    assert len(results) == 20


def test_validate_actions_tolerates_malformed_entries() -> None:
    proposed = [
        {},                              # missing action_type
        {"action_type": None},           # null action_type
        "not a dict",                    # type: ignore[list-item]
    ]
    results = validate_actions(proposed)  # type: ignore[arg-type]
    # All three become unknown-action records (allowed=False, review=True).
    assert all(not r.allowed for r in results)
    assert all(r.requires_human_review for r in results)
