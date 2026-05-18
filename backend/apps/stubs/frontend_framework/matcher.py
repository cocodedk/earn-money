"""Signature matcher + version extractor for stub 1.3 frontend-framework.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/03-frontend-framework.md
"""
from __future__ import annotations

import re
from typing import Any


EvidenceBundle = dict[str, Any]
Signature = dict[str, Any]


def match_signatures(
    signatures: list[Signature], bundle: EvidenceBundle
) -> list[Signature]:
    return [sig for sig in signatures if _matches(sig, bundle)]


def extract_version(signature: Signature, bundle: EvidenceBundle) -> str | None:
    """Apply `signature['version_regex']` to the haystack(s) implied by
    `signature['source']`. Returns capture group 1 of the first match,
    or None when the signature has no version_regex or the regex misses."""
    pattern = signature["version_regex"]
    if pattern is None:
        return None
    for haystack in _haystacks(signature, bundle):
        m = re.search(pattern, haystack)
        if m is not None:
            return m.group(1)
    return None


def _haystacks(signature: Signature, bundle: EvidenceBundle) -> list[str]:
    source = signature["source"]
    if source == "html_body":
        return [bundle.get("html_body", "")]
    if source == "script_src_path":
        return list(bundle.get("script_paths", []))
    if source == "asset_body":
        return list(bundle.get("asset_bodies", {}).values())
    return []  # pragma: no cover  # defense for an unknown source


def _matches(signature: Signature, bundle: EvidenceBundle) -> bool:
    haystacks = _haystacks(signature, bundle)
    if not haystacks:
        return False
    match_type = signature["match_type"]
    pattern = signature["value_pattern"]
    if match_type == "contains":
        return any(pattern in h for h in haystacks if h)
    if match_type == "regex":
        return any(re.search(pattern, h) is not None for h in haystacks if h)
    if match_type == "contains_all":
        return all(
            any(p in h for h in haystacks if h) for p in pattern
        )
    return False  # pragma: no cover  # defense for an unknown match_type
