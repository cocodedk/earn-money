"""Signature matcher + version extractor for stub 1.4 backend-hints.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/04-backend-hints.md
"""
from __future__ import annotations

import re
from typing import Any, Callable, Iterator


EvidenceBundle = dict[str, Any]
Signature = dict[str, Any]


def match_signatures(
    signatures: list[Signature], bundle: EvidenceBundle
) -> list[Signature]:
    return [sig for sig in signatures if _matches(sig, bundle)]


def extract_version(
    signature: Signature, bundle: EvidenceBundle
) -> str | None:
    """Apply `signature['version_regex']` to the value the signature
    matched. Returns capture group 1 or None when there is no
    version_regex / no match."""
    pattern = signature["version_regex"]
    if pattern is None:
        return None
    for value in _matched_values(signature, bundle):
        m = re.search(pattern, value)
        if m is not None:
            return m.group(1)
    return None


def _matches(signature: Signature, bundle: EvidenceBundle) -> bool:
    values = list(_matched_values(signature, bundle))
    if not values:
        return False
    match_type = signature["match_type"]
    pattern = signature["value_pattern"]
    if match_type == "exact":
        return pattern in values
    if match_type == "contains":
        return any(pattern in v for v in values)
    if match_type == "regex":
        return any(re.search(pattern, v) is not None for v in values)
    return False  # pragma: no cover  # defense for an unknown match_type


def _cookie_values(
    signature: Signature, bundle: EvidenceBundle
) -> Iterator[str]:
    for probe in bundle.get("probes", {}).values():
        for name in probe.get("cookies", []):
            yield name


def _header_values(
    signature: Signature, bundle: EvidenceBundle
) -> Iterator[str]:
    field = signature["field"]
    for probe in bundle.get("probes", {}).values():
        value = probe.get("headers", {}).get(field)
        if value is not None:
            yield value


def _body_values(
    signature: Signature, bundle: EvidenceBundle
) -> Iterator[str]:
    for probe in bundle.get("probes", {}).values():
        body = probe.get("body", "")
        if body:
            yield body


_SOURCE_DISPATCH: dict[
    str, Callable[[Signature, EvidenceBundle], Iterator[str]]
] = {
    "cookie": _cookie_values,
    "header": _header_values,
    "body": _body_values,
}


def _matched_values(
    signature: Signature, bundle: EvidenceBundle
) -> Iterator[str]:
    """Yield candidate strings to match against, dispatched on
    signature['source']. KeyError on an unknown source — the contract
    test (test_sources_are_in_allowed_set) prevents this in practice."""
    return _SOURCE_DISPATCH[signature["source"]](signature, bundle)
