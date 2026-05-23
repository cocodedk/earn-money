"""Stub 2.14 — redirect URI outcome classification."""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Literal
from urllib.parse import urlsplit

from apps.stubs._shared.types import Confidence

from apps.stubs._shared.url import origin


class ValidationResult(str, Enum):
    ACCEPTED_UNTRUSTED_REDIRECT = "accepted_untrusted_redirect"
    PRESERVED_UNTRUSTED_REDIRECT = "preserved_untrusted_redirect"
    REJECTED_INVALID_REDIRECT = "rejected_invalid_redirect"
    NOT_TESTED = "not_tested"
    INCONCLUSIVE = "inconclusive"


_REJECT_PHRASES = frozenset({
    "invalid_redirect_uri", "redirect_uri_mismatch",
    "invalid_request", "unauthorized_client",
})


@dataclass(frozen=True)
class RedirectUriClassification:
    validation_result: ValidationResult
    status: Literal["confirmed", "candidate", "rejected", "stale"]
    confidence: Confidence
    location_origin: str | None
    oauth_error: str | None


def classify_redirect_response(
    response: object,
    scanner_origin: str,
) -> RedirectUriClassification:
    """Classify a pre-auth authorization response against a mutated redirect URI."""
    status_code: int = getattr(response, "status_code", 0)
    headers: dict = getattr(response, "headers", {})
    body: str = getattr(response, "text", "") or ""

    # 3xx — check if Location points to scanner origin
    if 300 <= status_code < 400:
        location = headers.get("Location", "")
        if location:
            if origin(location) == origin(scanner_origin):
                return RedirectUriClassification(
                    validation_result=ValidationResult.ACCEPTED_UNTRUSTED_REDIRECT,
                    status="confirmed", confidence="high",
                    location_origin=urlsplit(location).netloc, oauth_error=None,
                )

    # 4xx — look for OAuth error phrases
    if status_code in (400, 401, 403):
        error = _extract_oauth_error(body, headers)
        if error and any(p in error for p in _REJECT_PHRASES):
            return RedirectUriClassification(
                validation_result=ValidationResult.REJECTED_INVALID_REDIRECT,
                status="rejected",
                confidence="high",
                location_origin=None,
                oauth_error=error,
            )

    # 200 — check if scanner URI appears in hidden field or form action
    if status_code == 200 and scanner_origin in body:
        return RedirectUriClassification(
            validation_result=ValidationResult.PRESERVED_UNTRUSTED_REDIRECT,
            status="candidate",
            confidence="medium",
            location_origin=None,
            oauth_error=None,
        )

    return RedirectUriClassification(
        validation_result=ValidationResult.INCONCLUSIVE,
        status="rejected",
        confidence="low",
        location_origin=None,
        oauth_error=None,
    )


def _extract_oauth_error(body: str, headers: dict) -> str | None:
    try:
        return json.loads(body).get("error", "")
    except Exception:
        pass
    for phrase in _REJECT_PHRASES:
        if phrase in body:
            return phrase
    return None
