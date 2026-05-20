"""Pure-function validators for stub 1.13 security.txt fields.

Spec §Detection logic Validation rules:
- Contact: at least one required; URI-like; accepted schemes
  mailto / https / http / tel.
- Expires: RFC3339/ISO-8601 timestamp; expired creates finding;
  malformed creates separate finding.
- Canonical: absolute HTTP(S) URL; must match final fetched URL.
- URL-valued fields (Policy, Encryption, Acknowledgments, Hiring,
  CSAF): shape only.

Validators stay pure — they don't fetch, log, or persist. The
classifier composes them into the 10 finding types.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/13-security-txt.md
"""
from __future__ import annotations

from datetime import datetime
from urllib.parse import urlsplit


# Spec §Validation: "Accepted schemes for this check: mailto, https,
# http, tel." Scheme strings are matched case-insensitively per
# RFC 3986 §3.1.
_CONTACT_SCHEMES: frozenset[str] = frozenset({
    "mailto", "https", "http", "tel",
})

_URL_SCHEMES: frozenset[str] = frozenset({"https", "http"})


def is_valid_contact(value: str) -> bool:
    """Return True when `value` looks like a Contact URI with an
    accepted scheme. Shape-only — the validator doesn't dial,
    email, or otherwise verify the contact target (spec §Safety
    Forbidden behavior: "calling contact addresses")."""
    if not value:
        return False
    scheme, sep, _rest = value.partition(":")
    if not sep:
        return False
    return scheme.lower() in _CONTACT_SCHEMES


def parse_expires(value: str) -> datetime | None:
    """Parse `value` as RFC3339/ISO-8601 timestamp. Returns the
    datetime or None when the value is empty or unparseable.
    Bare dates (no time component) are rejected per spec — Expires
    requires a timestamp."""
    if not value:
        return None
    normalised = value.strip()
    # Python's `datetime.fromisoformat` accepts the `Z` suffix on
    # 3.11+. Strip it as a belt-and-braces fallback.
    if normalised.endswith("Z"):
        normalised = normalised[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalised)
    except ValueError:
        return None
    # Require a time component — spec says "RFC3339/ISO-8601
    # *timestamp*". `fromisoformat("2027-01-01")` succeeds with
    # midnight; reject when the original value had no `T`.
    if "T" not in value and "t" not in value:
        return None
    return parsed


def is_expired(value: str, *, now: datetime) -> bool:
    """Return True when `value` parses as a timestamp older than
    `now`. Unparseable values return False — the classifier
    surfaces malformed dates separately."""
    parsed = parse_expires(value)
    if parsed is None:
        return False
    return parsed < now


def is_canonical_match(canonical: str, *, final_url: str) -> bool:
    """Return True when `canonical` matches the URL the runner
    actually fetched, modulo a trailing slash on either side."""
    return _normalise_url(canonical) == _normalise_url(final_url)


def is_valid_uri(value: str) -> bool:
    """Shape-only absolute-URL check. Used for Policy / Encryption
    / Acknowledgments / Hiring / CSAF fields."""
    if not value:
        return False
    parts = urlsplit(value)
    if parts.scheme.lower() not in _URL_SCHEMES:
        return False
    return bool(parts.netloc)


def _normalise_url(url: str) -> str:
    """Strip a single trailing slash from the path component so the
    canonical-match check tolerates a server that adds or strips
    it. Doesn't lowercase host — security.txt's authoritative
    Canonical entries are operator-controlled and case matters in
    some path components."""
    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    return f"{parts.scheme}://{parts.netloc}{path}"
