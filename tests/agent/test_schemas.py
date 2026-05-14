"""Tests for the scanner-analysis schema validator."""

from __future__ import annotations

import pytest

from earn_money.agent.schemas import (
    SCANNER_ANALYSIS_SCHEMA,
    InvalidScannerAnalysis,
    ScannerAnalysis,
    parse_scanner_analysis,
)


def _valid_payload() -> dict[str, object]:
    return {
        "finding_title": "Subdomain takeover via Heroku",
        "affected_asset": "mta-sts.example.com",
        "evidence_ids": ["ev-1", "ev-2"],
        "severity": "high",
        "confidence": "high",
        "reasoning_summary": "DNS CNAME points to unclaimed heroku app.",
        "remediation": "Reclaim the heroku app or remove the dangling CNAME.",
        "injection_suspected": False,
        "injection_indicators": [],
        "ignored_untrusted_instructions": [],
        "requires_human_review": False,
        "proposed_actions": [
            {
                "action_type": "draft_remediation",
                "risk_level": "low",
                "allowed": True,
                "reason": "ok",
            },
        ],
    }


def test_schema_block_has_openai_compatible_shape() -> None:
    assert SCANNER_ANALYSIS_SCHEMA["name"] == "scanner_analysis"
    schema = SCANNER_ANALYSIS_SCHEMA["schema"]
    assert isinstance(schema, dict)
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False


def test_parse_valid_payload_returns_dataclass() -> None:
    record = parse_scanner_analysis(_valid_payload())
    assert isinstance(record, ScannerAnalysis)
    assert record.finding_title == "Subdomain takeover via Heroku"
    assert record.severity == "high"
    assert record.confidence == "high"
    assert record.requires_human_review is False
    assert len(record.proposed_actions) == 1
    assert record.proposed_actions[0].action_type == "draft_remediation"


def test_parse_rejects_non_object() -> None:
    with pytest.raises(InvalidScannerAnalysis):
        parse_scanner_analysis("not an object")


@pytest.mark.parametrize("missing_field", [
    "finding_title", "affected_asset", "evidence_ids", "severity",
    "confidence", "reasoning_summary", "remediation",
    "injection_suspected", "injection_indicators",
    "ignored_untrusted_instructions", "requires_human_review",
])
def test_parse_rejects_missing_required_field(missing_field: str) -> None:
    payload = _valid_payload()
    del payload[missing_field]
    with pytest.raises(InvalidScannerAnalysis) as exc:
        parse_scanner_analysis(payload)
    assert missing_field in str(exc.value)


def test_parse_rejects_unknown_severity() -> None:
    payload = _valid_payload()
    payload["severity"] = "catastrophic"
    with pytest.raises(InvalidScannerAnalysis) as exc:
        parse_scanner_analysis(payload)
    assert "severity" in str(exc.value)


def test_parse_rejects_unknown_confidence() -> None:
    payload = _valid_payload()
    payload["confidence"] = "extremely_high"
    with pytest.raises(InvalidScannerAnalysis) as exc:
        parse_scanner_analysis(payload)
    assert "confidence" in str(exc.value)


def test_parse_rejects_non_bool_for_boolean_field() -> None:
    payload = _valid_payload()
    payload["injection_suspected"] = "false"  # string, not bool
    with pytest.raises(InvalidScannerAnalysis):
        parse_scanner_analysis(payload)


def test_parse_rejects_non_list_evidence_ids() -> None:
    payload = _valid_payload()
    payload["evidence_ids"] = "ev-1"
    with pytest.raises(InvalidScannerAnalysis):
        parse_scanner_analysis(payload)


def test_parse_rejects_malformed_action_entry() -> None:
    payload = _valid_payload()
    payload["proposed_actions"] = [
        {"action_type": "classify_finding"},  # missing risk_level/allowed/reason
    ]
    with pytest.raises(InvalidScannerAnalysis):
        parse_scanner_analysis(payload)


def test_parse_accepts_empty_action_list() -> None:
    payload = _valid_payload()
    payload["proposed_actions"] = []
    record = parse_scanner_analysis(payload)
    assert record.proposed_actions == ()
