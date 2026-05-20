"""Header matcher + version extractor for stub 1.2 server-headers.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/02-server-headers.md
"""
from __future__ import annotations

import re
from typing import Any


HeaderBundle = dict[str, str]
Signature = dict[str, Any]


def normalize_headers(headers: HeaderBundle) -> HeaderBundle:
    return {name.lower(): value for name, value in headers.items()}


def match_signatures(
    signatures: list[Signature], headers: HeaderBundle
) -> list[Signature]:
    norm = normalize_headers(headers)
    return [sig for sig in signatures if _matches(sig, norm)]


def extract_version(
    signature: Signature, norm_headers: HeaderBundle
) -> str | None:
    """Apply `signature['version_regex']` to the header value.

    `norm_headers` must already be lowercase-keyed (callers feed the
    output of `normalize_headers` — see test for the contract). Returns
    capture group 1, or None when there is no version_regex, the
    header is absent, or the regex misses."""
    pattern = signature["version_regex"]
    if pattern is None:
        return None
    value = norm_headers.get(signature["header_name"])
    if value is None:
        return None
    m = re.search(pattern, value)
    if m is None:
        return None
    return m.group(1)


def _matches(signature: Signature, norm_headers: HeaderBundle) -> bool:
    value = norm_headers.get(signature["header_name"])
    if value is None:
        return False
    match_type = signature["match_type"]
    pattern = signature["value_pattern"]
    if match_type == "exact":
        return value == pattern
    if match_type == "contains":
        return pattern.lower() in value.lower()
    if match_type == "regex":
        return re.search(pattern, value) is not None
    return False  # pragma: no cover  # defense for an unknown match_type
