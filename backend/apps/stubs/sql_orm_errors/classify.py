"""Confidence + severity classifier for stub 1.19 sql_orm_errors.

Spec §Classification ladder:
  high   = strong signature (requires_context=False) + error_status (≥400)
           OR strong signature + SQL/driver/table-column context lift
  medium = strong signature (requires_context=False) on OK status
           OR medium-hint signature with error_status
  low    = weak signature (requires_context=True) alone
  none   = no signature match → return None (no Verdict, no Finding)

Spec §Severity guidance (HARD CAP at medium):
  info    = default for generic ORM class disclosure
  low     = DB type / driver / SQL fragment / table-column / stack-frame
  medium  = sensitive schema or query fragments materially help exploit
  high/critical = FORBIDDEN for this check (spec §Severity guidance #4)

The classifier returns a `Verdict` NamedTuple; the runner (slice 19-C)
combines it with persisted Evidence to write `SqlOrmErrorFinding`.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/19-sql-orm-errors.md
"""
from __future__ import annotations

from typing import Literal, Mapping, NamedTuple, Optional

from .._shared.types import Confidence
from .signals import Match, find_strongest_signal


Severity = Literal["info", "low", "medium"]
_ERROR_STATUS_THRESHOLD = 400
_EXCERPT_HALF_WIDTH = 120


class Verdict(NamedTuple):
    confidence: Confidence
    signature_id: str
    signature_family: str
    error_excerpt: str
    severity: Severity


def classify(
    *,
    status: int,
    headers: Mapping[str, str],
    body: bytes,
) -> Optional[Verdict]:
    """Match `body` against the signature table and ladder-up a Verdict.

    `status` lifts a `requires_context` signature when it's ≥400.
    `headers` is unused in MVP — RFC 7807 / content-type handling is
    classifier-level info but doesn't change the ladder today.
    """
    match = find_strongest_signal(body)
    if match is None:
        return None

    sig = match.signature
    is_error_status = status >= _ERROR_STATUS_THRESHOLD

    # Every current signature is either (high, no-context) — strong alone
    # — or (medium/low, requires-context) — weak. The classifier ladder
    # for strong-alone lifts on error status; everything else is "low"
    # until a richer context-evidence model lands (follow-up).
    if sig.confidence_hint == "high" and not sig.requires_context:
        confidence: Confidence = "high" if is_error_status else "medium"
    else:
        confidence = "low"

    return Verdict(
        confidence=confidence,
        signature_id=sig.id,
        signature_family=sig.family,
        error_excerpt=_excerpt_around(body, match),
        severity=_severity_for(confidence),
    )


def _excerpt_around(body: bytes, match: Match) -> str:
    """Slice ±120 bytes around the match offset; decode safely."""
    start = max(0, match.offset - _EXCERPT_HALF_WIDTH)
    end = min(len(body), match.offset + len(match.matched_text.encode()) + _EXCERPT_HALF_WIDTH)
    return body[start:end].decode("utf-8", errors="replace")


def _severity_for(confidence: Confidence) -> Severity:
    """Spec §Severity: cap at medium. Higher confidence → higher severity."""
    if confidence == "high":
        return "medium"
    if confidence == "medium":
        return "low"
    return "info"
