"""Body-canonicalisation helpers for `normalize`.

Strips CSRF tokens, UUIDs, ISO timestamps, long random tokens, and
whitespace so two probes that differ only in per-request randomness
hash to the same fingerprint.
"""
from __future__ import annotations

import re


_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_HIDDEN_INPUT_VALUE_RE = re.compile(
    r'(<input[^>]*type="hidden"[^>]*value=")[^"]*(")',
    flags=re.IGNORECASE,
)
_TIMESTAMP_ISO_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"
)
_LONG_TOKEN_RE = re.compile(r"\b[A-Za-z0-9_\-]{32,}\b")


def canonicalise_body(body: str) -> str:
    """Strip dynamic values so two probes that differ only on CSRF /
    UUID / timestamp / random-token bytes hash to the same string."""
    out = body
    out = _HIDDEN_INPUT_VALUE_RE.sub(r"\1__REDACTED__\2", out)
    out = _UUID_RE.sub("__UUID__", out)
    out = _TIMESTAMP_ISO_RE.sub("__TS__", out)
    out = _LONG_TOKEN_RE.sub("__TOKEN__", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def build_snippet(canonical_body: str, *, cap: int = 512) -> str:
    """Up-to-512-char excerpt near error-indicating keywords; falls back
    to the body head when no marker matched."""
    if not canonical_body:
        return ""
    lo = canonical_body.lower()
    for marker in ("error", "invalid", "incorrect", "not found", "unknown"):
        idx = lo.find(marker)
        if idx >= 0:
            start = max(0, idx - cap // 4)
            return canonical_body[start:start + cap]
    return canonical_body[:cap]
