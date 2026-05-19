"""Secret detection + redaction for stub 1.15.

Spec §4 'Secret handling' + §Safety: scan the bundle body for
high-signal token shapes. Each match becomes a ``TokenIndicator``
that carries:

* `kind` — the detector classification
* `redacted_preview` — first 4 chars + a masked tail; the raw
  value MUST NOT appear anywhere in the indicator
* `length` — char length of the raw value (forensic hint)
* `sha256` — hex digest of the raw value so the same secret can
  be correlated across scans without re-leaking it

Detectors are intentionally narrow and high-signal. JWTs are
anchored on the `eyJ...` base64-encoded `{"...` header so an IP
like `1.2.3.4` can't false-positive. AWS access keys require the
full `AKIA` + 16-char tail. URL-with-credentials needs both a user
and a password separated by `:`.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/15-public-javascript-bundles.md
"""
from __future__ import annotations

import re
from typing import Literal, NamedTuple

from .._shared.hashing import body_hash_bytes


TokenKind = Literal[
    "jwt", "aws_access_key", "url_with_credentials", "bearer_token",
]


class TokenIndicator(NamedTuple):
    kind: TokenKind
    redacted_preview: str
    length: int
    sha256: str


_JWT_RE = re.compile(
    r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"
)
_AWS_KEY_RE = re.compile(r"\bAKIA[A-Z0-9]{16}\b")
_URL_WITH_CREDS_RE = re.compile(
    r"https?://[^\s/'\"<>:@]+:[^\s/'\"<>@]+@[A-Za-z0-9.\-]+(?:/[^\s'\"<>]*)?"
)
_BEARER_TOKEN_RE = re.compile(
    r"Bearer\s+([A-Za-z0-9_\-.~+/=]{20,})"
)


_DETECTORS: tuple[tuple[TokenKind, re.Pattern[str]], ...] = (
    ("jwt", _JWT_RE),
    ("aws_access_key", _AWS_KEY_RE),
    ("url_with_credentials", _URL_WITH_CREDS_RE),
    ("bearer_token", _BEARER_TOKEN_RE),
)


def _redact(raw: str) -> str:
    """Show first 4 chars + asterisks. The 4-char prefix is
    deliberately preserved — JWT/AKIA/`http://` are public-by-design
    class markers and the operator needs SOME breadcrumb to triage.
    All detector regexes enforce a minimum length of 9 (JWT) or
    higher, so the prefix is always a small fraction of the raw
    value. A future detector with shorter tokens must add a short-
    value branch with its own redaction test."""
    return raw[:4] + "*" * max(len(raw) - 4, 0)


def extract_token_indicators(body: str) -> list[TokenIndicator]:
    seen: set[str] = set()
    out: list[TokenIndicator] = []
    for kind, pattern in _DETECTORS:
        for match in pattern.finditer(body):
            raw = match.group(1) if pattern.groups else match.group(0)
            if raw in seen:
                continue
            seen.add(raw)
            out.append(TokenIndicator(
                kind=kind,
                redacted_preview=_redact(raw),
                length=len(raw),
                sha256=body_hash_bytes(raw.encode("utf-8")),
            ))
    return out
