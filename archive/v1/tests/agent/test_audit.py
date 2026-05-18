"""Tests for the agent audit log + redaction."""

from __future__ import annotations

import json
from pathlib import Path

from earn_money.agent.audit import (
    AuditEvent,
    audit_root_for,
    record,
    redact,
)


def _ev(**overrides: object) -> AuditEvent:
    base: dict[str, object] = {
        "event_type": "agent_decision",
        "platform": "hackerone",
        "slug": "example",
        "timestamp": "2026-05-14T12:00:00Z",
    }
    base.update(overrides)
    return AuditEvent(**base)  # type: ignore[arg-type]


def test_record_appends_jsonl_line_to_per_day_file(tmp_path: Path) -> None:
    audit_root = tmp_path / "audit"
    target = record(audit_root, _ev())
    assert target.exists()
    assert target.suffix == ".jsonl"
    lines = target.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record_dict = json.loads(lines[0])
    assert record_dict["event_type"] == "agent_decision"
    assert record_dict["platform"] == "hackerone"


def test_record_appends_repeated_calls(tmp_path: Path) -> None:
    audit_root = tmp_path / "audit"
    record(audit_root, _ev())
    record(audit_root, _ev(slug="another"))
    record(audit_root, _ev(slug="third"))
    target = next(audit_root.iterdir())
    lines = target.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    parsed = [json.loads(line) for line in lines]
    assert [row["slug"] for row in parsed] == ["example", "another", "third"]


def test_redact_anthropic_api_key() -> None:
    out = redact("token=sk-ant-abcdefghijklmnopqrstuvwx other text")
    # sk-ant-* prefix takes precedence over generic sk-*
    assert out == "token=sk-ant-… other text"


def test_redact_openai_style_api_key() -> None:
    out = redact("key sk-abcdefghijklmnopqrstuvwx in url")
    assert "sk-abcdefghij" not in out
    assert "sk-…" in out


def test_redact_huggingface_token() -> None:
    assert "hf_…" in redact("export HF_API_KEY=hf_abcdefghijklmnopqrstuv")


def test_redact_bearer_token() -> None:
    out = redact("Authorization: Bearer abcdefghijklmnopqrstuvwx")
    # Authorization header takes precedence
    assert "[REDACTED]" in out


def test_redact_aws_access_key() -> None:
    out = redact("const k = AKIAIOSFODNN7EXAMPLE;")
    assert "AKIA…" in out
    assert "AKIAIOSFODNN7EXAMPLE" not in out


def test_redact_github_pat() -> None:
    out = redact("token=ghp_abcdefghijklmnopqrstuvwxyz0123456789ab")
    assert "ghp_abcdefg" not in out


def test_redact_slack_token() -> None:
    out = redact("hook=xoxb-1234567890-1234567890123-abcdefABCDEF1234567890ab")
    assert "xox…" in out


def test_redact_cookie_header() -> None:
    out = redact("Cookie: session=abcdef123; uid=42")
    assert "REDACTED" in out


def test_redact_walks_nested_structures() -> None:
    payload = {
        "evidence": [
            {"body": "Authorization: Bearer abcdefghij1234567890"},
            ("nested tuple", "with sk-abcdefghijklmnopqrstuvwx"),
        ],
        "meta": "ghp_abcdefghijklmnopqrstuvwxyz0123456789ab leaked",
    }
    cleaned = redact(payload)
    serialized = json.dumps(cleaned, default=str)
    assert "Bearer abcdefghij" not in serialized
    assert "sk-abcdefghij" not in serialized
    assert "ghp_abcdefghij" not in serialized


def test_record_redacts_before_writing(tmp_path: Path) -> None:
    audit_root = tmp_path / "audit"
    record(audit_root, _ev(
        proposed_actions=(
            {"action_type": "classify_finding",
             "reason": "see sk-abcdefghijklmnopqrstuvwx in evidence"},
        ),
    ))
    raw = next(audit_root.iterdir()).read_text(encoding="utf-8")
    assert "sk-abcdefghij" not in raw
    assert "sk-…" in raw


def test_audit_root_for_returns_scratch_path(tmp_path: Path) -> None:
    root = audit_root_for(tmp_path)
    assert root == tmp_path / "scratch" / "agent-audit"
