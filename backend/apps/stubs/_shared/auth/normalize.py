"""Response normalization + diff + abort-signal classification.

`normalize()` strips dynamic values (CSRF tokens, session cookies,
UUIDs, timestamps, request IDs) from a raw httpx.Response so two
probes against the same endpoint can be compared without false
positives on per-request randomness.

`diff()` reports semantically meaningful differences between two
normalized responses — status, redirect, JSON error code, title,
body fingerprint — never raw header / cookie / token bytes.

`classify_abort()` re-exposes the CAPTCHA / WAF / lockout / rate-
limit / MFA signal already computed during normalization. A scan
that hits one of these must NOT promote findings to `confirmed`;
the safety helper records `stale` or an event-only refusal.

Internals split into `_normalize_strip.py`, `_normalize_parse.py`,
`_normalize_abort.py` to stay under the 200-line cap.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Literal

from . import _normalize_abort as _abort
from . import _normalize_parse as _parse
from . import _normalize_strip as _strip
from .safety import AbortSignal


@dataclass(frozen=True)
class Differentiator:
    kind: Literal[
        "status_code", "redirect_location", "json_error_code",
        "field_error", "body_text", "title_text",
    ]
    invalid_value_redacted: str
    valid_value_redacted: str
    explanation: str


@dataclass(frozen=True)
class NormalizedResponse:
    status: int
    final_url: str
    redirect_location: str | None
    content_type: str
    title: str | None
    body_fingerprint: str
    body_snippet: str
    json_error_code: str | None
    json_error_fields: dict[str, str] = field(default_factory=dict)
    abort_signal: AbortSignal | None = None


def normalize(response: Any) -> NormalizedResponse:
    """Build a `NormalizedResponse` from an httpx.Response-like object."""
    raw_body = response.text or ""
    headers = response.headers or {}
    content_type = _parse.coerce_str(
        headers.get("content-type", "")
    ).split(";")[0].strip()

    json_error_code, json_error_fields = _parse.parse_json_errors(
        raw_body, content_type,
    )
    title = _parse.extract_title(raw_body) if "html" in content_type.lower() else None
    body_canon = _strip.canonicalise_body(raw_body)
    body_fingerprint = hashlib.sha256(body_canon.encode("utf-8")).hexdigest()
    body_snippet = _strip.build_snippet(body_canon)
    abort_signal = _abort.classify_abort_body(raw_body)

    return NormalizedResponse(
        status=int(response.status_code),
        final_url=str(response.url),
        redirect_location=_parse.coerce_optional_str(headers.get("location")),
        content_type=content_type,
        title=title,
        body_fingerprint=body_fingerprint,
        body_snippet=body_snippet,
        json_error_code=json_error_code,
        json_error_fields=json_error_fields,
        abort_signal=abort_signal,
    )


def diff(a: NormalizedResponse, b: NormalizedResponse) -> list[Differentiator]:
    """Return semantically meaningful differences between two normalized
    responses. Empty list = no signal. Body-byte differences surface as
    one `body_text` differentiator (weak signal per spec 2.1 §5)."""
    out: list[Differentiator] = []
    if a.status != b.status:
        out.append(Differentiator(
            kind="status_code",
            invalid_value_redacted=str(a.status),
            valid_value_redacted=str(b.status),
            explanation="HTTP status differs between controls",
        ))
    if a.redirect_location != b.redirect_location:
        out.append(Differentiator(
            kind="redirect_location",
            invalid_value_redacted=a.redirect_location or "",
            valid_value_redacted=b.redirect_location or "",
            explanation="Redirect target differs between controls",
        ))
    if a.json_error_code != b.json_error_code:
        out.append(Differentiator(
            kind="json_error_code",
            invalid_value_redacted=a.json_error_code or "",
            valid_value_redacted=b.json_error_code or "",
            explanation="JSON error code differs between controls",
        ))
    if a.title != b.title:
        out.append(Differentiator(
            kind="title_text",
            invalid_value_redacted=a.title or "",
            valid_value_redacted=b.title or "",
            explanation="Response page title differs",
        ))
    if a.body_fingerprint != b.body_fingerprint and not _has_strong_signal(out):
        out.append(Differentiator(
            kind="body_text",
            invalid_value_redacted=a.body_snippet,
            valid_value_redacted=b.body_snippet,
            explanation="Response body text differs after normalization",
        ))
    return out


def classify_abort(response: NormalizedResponse) -> AbortSignal | None:
    """Re-expose the abort signal already computed during normalization."""
    return response.abort_signal


def _has_strong_signal(differentiators: list[Differentiator]) -> bool:
    """True when a stronger differentiator already covers the body change."""
    strong = {"status_code", "redirect_location", "json_error_code", "title_text"}
    return any(d.kind in strong for d in differentiators)
