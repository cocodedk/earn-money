"""JSON-Schema and dataclass shapes for structured LLM outputs (spec §11).

The schema is the one OpenRouter / OpenAI consume via `response_format`.
The dataclass mirrors it for Python-side typing + the application-code
validator that runs on every reply, regardless of whether the model
claimed to honor the schema.

Validation is intentionally hand-rolled — no `jsonschema` dep — because
the surface is small, stable, and we want every check to be auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SCHEMA_VERSION = "v1.2026-05-14"

# Spec §11. Keys + types match the spec verbatim; field names use
# snake_case throughout. `proposed_actions` is open-ended on the wire;
# the action_allowlist validator clamps the values to its own table.
SCANNER_ANALYSIS_SCHEMA: dict[str, object] = {
    "name": "scanner_analysis",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "finding_title", "affected_asset", "evidence_ids",
            "severity", "confidence", "reasoning_summary",
            "remediation", "injection_suspected",
            "injection_indicators", "ignored_untrusted_instructions",
            "requires_human_review", "proposed_actions",
        ],
        "properties": {
            "finding_title": {"type": "string"},
            "affected_asset": {"type": "string"},
            "evidence_ids": {"type": "array", "items": {"type": "string"}},
            "severity": {
                "type": "string",
                "enum": ["info", "low", "medium", "high", "critical"],
            },
            "confidence": {
                "type": "string",
                "enum": ["low", "medium", "high"],
            },
            "reasoning_summary": {"type": "string"},
            "remediation": {"type": "string"},
            "injection_suspected": {"type": "boolean"},
            "injection_indicators": {
                "type": "array", "items": {"type": "string"},
            },
            "ignored_untrusted_instructions": {
                "type": "array", "items": {"type": "string"},
            },
            "requires_human_review": {"type": "boolean"},
            "proposed_actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "action_type", "risk_level", "allowed", "reason",
                    ],
                    "properties": {
                        "action_type": {"type": "string"},
                        "risk_level": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                        },
                        "allowed": {"type": "boolean"},
                        "reason": {"type": "string"},
                    },
                },
            },
        },
    },
}

_ALLOWED_SEVERITY = frozenset({"info", "low", "medium", "high", "critical"})
_ALLOWED_CONFIDENCE = frozenset({"low", "medium", "high"})
_ALLOWED_RISK = frozenset({"low", "medium", "high"})


@dataclass(frozen=True)
class ProposedAction:
    action_type: str
    risk_level: str
    allowed: bool
    reason: str


@dataclass(frozen=True)
class ScannerAnalysis:
    finding_title: str
    affected_asset: str
    evidence_ids: tuple[str, ...]
    severity: str
    confidence: str
    reasoning_summary: str
    remediation: str
    injection_suspected: bool
    injection_indicators: tuple[str, ...]
    ignored_untrusted_instructions: tuple[str, ...]
    requires_human_review: bool
    proposed_actions: tuple[ProposedAction, ...] = field(default_factory=tuple)


class InvalidScannerAnalysis(Exception):
    """Raised when a payload doesn't match the scanner-analysis schema."""


def parse_scanner_analysis(payload: object) -> ScannerAnalysis:
    """Validate `payload` (a parsed-JSON dict) and return a typed record.

    Raises `InvalidScannerAnalysis` with the offending field on any
    shape/type/enum violation. The application MUST run this on every
    reply — `response_format` is best-effort on the wire.
    """
    if not isinstance(payload, dict):
        raise InvalidScannerAnalysis(f"expected object, got {type(payload).__name__}")
    return ScannerAnalysis(
        finding_title=_req_str(payload, "finding_title"),
        affected_asset=_req_str(payload, "affected_asset"),
        evidence_ids=_req_str_tuple(payload, "evidence_ids"),
        severity=_req_enum(payload, "severity", _ALLOWED_SEVERITY),
        confidence=_req_enum(payload, "confidence", _ALLOWED_CONFIDENCE),
        reasoning_summary=_req_str(payload, "reasoning_summary"),
        remediation=_req_str(payload, "remediation"),
        injection_suspected=_req_bool(payload, "injection_suspected"),
        injection_indicators=_req_str_tuple(payload, "injection_indicators"),
        ignored_untrusted_instructions=_req_str_tuple(
            payload, "ignored_untrusted_instructions",
        ),
        requires_human_review=_req_bool(payload, "requires_human_review"),
        proposed_actions=_parse_actions(payload.get("proposed_actions") or []),
    )


def _req_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise InvalidScannerAnalysis(f"{key}: expected string, got {type(value).__name__}")
    return value


def _req_bool(payload: dict[str, object], key: str) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        raise InvalidScannerAnalysis(f"{key}: expected boolean, got {type(value).__name__}")
    return value


def _req_str_tuple(payload: dict[str, object], key: str) -> tuple[str, ...]:
    value = payload.get(key)
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise InvalidScannerAnalysis(f"{key}: expected list[string]")
    return tuple(value)


def _req_enum(payload: dict[str, object], key: str, allowed: frozenset[str]) -> str:
    value = _req_str(payload, key)
    if value not in allowed:
        raise InvalidScannerAnalysis(
            f"{key}: must be one of {sorted(allowed)}, got {value!r}"
        )
    return value


def _parse_actions(value: object) -> tuple[ProposedAction, ...]:
    if not isinstance(value, list):
        raise InvalidScannerAnalysis("proposed_actions: expected list")
    out: list[ProposedAction] = []
    for idx, entry in enumerate(value):
        if not isinstance(entry, dict):
            raise InvalidScannerAnalysis(f"proposed_actions[{idx}]: expected object")
        risk = _req_enum(entry, "risk_level", _ALLOWED_RISK)
        out.append(ProposedAction(
            action_type=_req_str(entry, "action_type"),
            risk_level=risk,
            allowed=_req_bool(entry, "allowed"),
            reason=_req_str(entry, "reason"),
        ))
    return tuple(out)
