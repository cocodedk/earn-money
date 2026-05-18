"""Signature matcher for framework-detection.

Pure functions over an evidence bundle (a dict of pre-extracted values).
Match types currently in use: equals, contains, contains_all. Add new
ones inline as the signature library grows.
"""
from __future__ import annotations

from typing import Any


EvidenceBundle = dict[str, Any]


def extract(bundle: EvidenceBundle, source: str, field: str) -> list[str]:
    """Return the candidate strings to match against, per (source, field).

    Unknown (source, field) combinations return [] so the matcher cleanly
    reports "no match" rather than crashing on a signature that names a
    source we don't collect yet.
    """
    if source == "cookie":
        return [
            c.get(field, "") for c in bundle.get("cookies", [])
            if c.get(field) is not None
        ]
    if source == "header":
        return [bundle.get("headers", {}).get(field, "")]
    if source == "html" and field == "body":
        return [bundle.get("html_body", "")]
    if source == "html" and field == "script_names":
        return list(bundle.get("script_names", []))
    return []


def matches(signature: dict[str, Any], bundle: EvidenceBundle) -> bool:
    """Return True if the signature's pattern matches any extracted value."""
    values = extract(bundle, signature["source"], signature["field"])
    if not values:
        return False
    match_type = signature["match_type"]
    if match_type == "equals":
        return signature["pattern"] in values
    if match_type == "contains":
        pattern = signature["pattern"]
        return any(pattern in value for value in values if value)
    if match_type == "contains_all":
        patterns = signature["patterns"]
        return all(
            any(p in value for value in values if value) for p in patterns
        )
    return False  # pragma: no cover  # defense for an unknown match_type
