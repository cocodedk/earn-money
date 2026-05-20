"""Signature matcher + version extractor for stub 1.4 backend-hints.

`find_first_match` is the load-bearing primitive: it returns the
probe path and the actual matched value (not just a boolean), so the
runner can attribute Evidence to the specific probe that fired and
persist the real matched string rather than the signature pattern.
`match_signatures` and `extract_version` build on it.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/04-backend-hints.md
"""
from __future__ import annotations

import re
from typing import Any, Iterator


EvidenceBundle = dict[str, Any]
Signature = dict[str, Any]


def match_signatures(
    signatures: list[Signature], bundle: EvidenceBundle
) -> list[Signature]:
    return [
        sig for sig in signatures
        if find_first_match(sig, bundle) is not None
    ]


def find_first_match(
    signature: Signature, bundle: EvidenceBundle
) -> tuple[str, str] | None:
    """Return (probe_path, matched_value) for the first probe whose
    candidate value satisfies the signature, or None."""
    for path, probe in bundle.get("probes", {}).items():
        for value in _values_from_probe(signature, probe):
            if _value_matches(signature, value):
                return path, value
    return None


def extract_version(
    signature: Signature, bundle: EvidenceBundle
) -> str | None:
    """Apply `signature['version_regex']` to the value the signature
    matched. Returns capture group 1 or None when there is no
    version_regex / no match."""
    pattern = signature["version_regex"]
    if pattern is None:
        return None
    result = find_first_match(signature, bundle)
    if result is None:
        return None
    _, matched_value = result
    m = re.search(pattern, matched_value)
    if m is None:
        return None
    return m.group(1)


def _cookie_values(_signature: Signature, probe: dict) -> Iterator[str]:
    yield from probe.get("cookies", [])


def _header_values(signature: Signature, probe: dict) -> Iterator[str]:
    value = probe.get("headers", {}).get(signature["field"])
    if value is not None:
        yield value


def _body_values(_signature: Signature, probe: dict) -> Iterator[str]:
    body = probe.get("body", "")
    if body:
        yield body


_SOURCE_DISPATCH = {
    "cookie": _cookie_values,
    "header": _header_values,
    "body": _body_values,
}


def _values_from_probe(
    signature: Signature, probe: dict
) -> Iterator[str]:
    """Yield candidate strings from the probe, per signature['source'].
    KeyError on an unknown source — contract test prevents this."""
    return _SOURCE_DISPATCH[signature["source"]](signature, probe)


def _value_matches(signature: Signature, value: str) -> bool:
    match_type = signature["match_type"]
    pattern = signature["value_pattern"]
    if match_type == "exact":
        return value == pattern
    if match_type == "contains":
        return pattern in value
    if match_type == "regex":
        return re.search(pattern, value) is not None
    return False  # pragma: no cover  # contract test prevents unknown match_types
