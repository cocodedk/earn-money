"""Confidence + status classifier for stub 1.17 (slice 2).

Spec §"Confidence rules" + §"Status rules". Pure function from
(indicators list, response status, content type) → typed Verdict.
Returns None when no indicators were found — no finding to persist.

* `high` — error status + at least one strong indicator
  (stack/source path/exception/database error). Multiple strong
  indicators on the same response also land here per spec.
* `medium` — 200 response with a clear JSON debug field
  (developer-mode API errors that didn't bump the status code).
* `low` — single weak signal (currently: only a source path on a
  non-error response). Surfaces as `candidate`, not `confirmed`,
  so a follow-up probe can promote it.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/17-verbose-api-errors.md
"""
from __future__ import annotations

from typing import Literal, NamedTuple

from .._shared.types import Confidence
from .indicators import ApiErrorIndicator


Status = Literal["candidate", "confirmed", "rejected", "stale"]

_ERROR_STATUS_THRESHOLD = 400
_STRONG_KINDS = frozenset({
    "json_debug_field", "source_path", "database_error",
})


class Verdict(NamedTuple):
    confidence: Confidence
    status: Status


def classify(
    indicators: list[ApiErrorIndicator], *,
    response_status: int, content_type: str,
) -> Verdict | None:
    if not indicators:
        return None
    is_error_response = response_status >= _ERROR_STATUS_THRESHOLD
    kinds = {ind.kind for ind in indicators}
    has_json_field = "json_debug_field" in kinds
    is_json_response = "json" in content_type.lower()

    if is_error_response and (kinds & _STRONG_KINDS):
        return Verdict(confidence="high", status="confirmed")
    if has_json_field and is_json_response:
        return Verdict(confidence="medium", status="confirmed")
    return Verdict(confidence="low", status="candidate")
