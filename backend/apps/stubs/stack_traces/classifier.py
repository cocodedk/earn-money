"""Confidence + status classifier for stub 1.16 (slice 3).

Spec §"Confidence rules" + §"Status rules". Combines the matcher's
output (slice 1) with the docs-like heuristic (slice 2) and the
HTTP response status into a typed Verdict.

Returns None when no matches were emitted — no finding to persist.
A docs-like response with a match collapses to (low, rejected) per
spec §"False-positive checks"; otherwise the strongest match
drives a (confidence, confirmed) verdict.

The runner (slice 4) consumes the Verdict directly; the 'stale'
status is runner-applied during cross-run reconciliation and never
emitted from this function.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/16-stack-traces.md
"""
from __future__ import annotations

from typing import Literal, NamedTuple

from .._shared.types import Confidence
from .matcher import StackTraceMatch


Status = Literal["candidate", "confirmed", "rejected", "stale"]

_ERROR_STATUS_THRESHOLD = 400
_GENERIC_FAMILIES: frozenset[str] = frozenset({
    "generic_stack_trace", "path_line_leak",
})


class Verdict(NamedTuple):
    confidence: Confidence
    status: Status


def classify(
    matches: list[StackTraceMatch],
    *,
    response_status: int,
    is_docs_like: bool,
) -> Verdict | None:
    if not matches:
        return None
    if is_docs_like:
        return Verdict(confidence="low", status="rejected")
    best = _strongest(matches)
    return Verdict(
        confidence=_confidence_for(best, response_status),
        status="confirmed",
    )


def _confidence_for(
    match: StackTraceMatch, response_status: int,
) -> Confidence:
    has_exception = match.exception_type is not None
    is_known_family = match.family not in _GENERIC_FAMILIES
    is_error_response = response_status >= _ERROR_STATUS_THRESHOLD

    qualifies_for_high = (
        is_known_family
        and is_error_response
        and (
            match.stack_frame_count >= 2
            or (match.stack_frame_count >= 1 and has_exception)
        )
    )
    if qualifies_for_high:
        return "high"

    qualifies_for_medium = (
        is_known_family
        and match.stack_frame_count >= 1
        and (has_exception or match.framework is not None)
    )
    if qualifies_for_medium:
        return "medium"

    return "low"


def _strongest(matches: list[StackTraceMatch]) -> StackTraceMatch:
    """Pick the match with the highest signal: more frames > with
    exception > framework set > known (non-generic) family. Ties
    break on first-seen so deterministic ordering across runs is
    preserved when two equally strong matches appear."""
    def score(m: StackTraceMatch) -> tuple[int, int, int, int]:
        return (
            m.stack_frame_count,
            1 if m.exception_type else 0,
            1 if m.framework else 0,
            0 if m.family in _GENERIC_FAMILIES else 1,
        )
    return max(matches, key=score)
