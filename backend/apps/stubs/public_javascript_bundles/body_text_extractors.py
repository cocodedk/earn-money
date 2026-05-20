"""Body-text extractors for stub 1.15 — public API/env/suspicious.

Spec §4 "Public route/API hints", "Public environment/config names",
"Suspicious but non-secret indicators". These three extractors run
against the decoded bundle body and return deduplicated, first-seen-
order lists of matched tokens.

* extract_api_path_hints — captures `/api/...`, `/graphql`,
  `/rest/...`, `/v1/...`, `/v2/...` URL tokens. The negative
  lookahead `(?![A-Za-z0-9_])` blocks `/apiary` and similar
  prefix-collision false positives.
* extract_public_env_names — captures variable NAMES with the
  framework public-prefix vocabulary (PUBLIC_, NEXT_PUBLIC_,
  VITE_, REACT_APP_, NUXT_PUBLIC_). Values are NOT returned —
  the spec routes value redaction through the secret_redactors
  module (slice 5b).
* extract_suspicious_indicators — localhost / RFC 1918 private IP
  literals / 0.0.0.0 / staging+dev hostnames. Each is a
  deterministic non-secret marker; severity stays `info` per spec.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/15-public-javascript-bundles.md
"""
from __future__ import annotations

import re
from typing import Iterable


# Longer alternatives first so NEXT_PUBLIC_x doesn't degrade into
# PUBLIC_x — regex alternation is left-to-right.
_PUBLIC_ENV_RE = re.compile(
    r"\b(?:NEXT_PUBLIC|NUXT_PUBLIC|REACT_APP|PUBLIC|VITE)_[A-Z0-9_]+\b"
)

# Path token: the prefix MUST be followed by a non-word char (or
# end of input). The `(?:/[A-Za-z0-9._\-~]+)*` tail captures nested
# segments like `/api/v1/admin/users`.
_API_PATH_RE = re.compile(
    r"/(?:api|graphql|rest|v[12])(?![A-Za-z0-9_])(?:/[A-Za-z0-9._\-~]+)*"
)

# RFC 1918 private ranges + localhost markers. Word boundaries keep
# the 4-octet match from running into a longer numeric string in a
# hash or build manifest.
_SUSPICIOUS_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\blocalhost\b"),
    re.compile(r"\b127\.0\.0\.1\b"),
    re.compile(r"\b0\.0\.0\.0\b"),
    re.compile(r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
    re.compile(r"\b192\.168\.\d{1,3}\.\d{1,3}\b"),
    re.compile(r"\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b"),
    re.compile(r"\b(?:staging|dev)\.[a-z0-9][a-z0-9.\-]+\b"),
)


def _dedupe_preserving_order(items: Iterable[str]) -> list[str]:
    """First-seen wins. dict insertion order is stable on 3.7+ so
    `dict.fromkeys` is the canonical idiom for this."""
    return list(dict.fromkeys(items))


def extract_api_path_hints(body: str) -> list[str]:
    return _dedupe_preserving_order(_API_PATH_RE.findall(body))


def extract_public_env_names(body: str) -> list[str]:
    return _dedupe_preserving_order(_PUBLIC_ENV_RE.findall(body))


def extract_suspicious_indicators(body: str) -> list[str]:
    matches: list[str] = []
    for pattern in _SUSPICIOUS_PATTERNS:
        matches.extend(pattern.findall(body))
    return _dedupe_preserving_order(matches)
