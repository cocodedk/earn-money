"""Signature table contract for stub 1.3 frontend-framework."""
from __future__ import annotations

import re
import unittest

from apps.findings.confidence import CONFIDENCE_RANK

from ..signatures import CATEGORIES, MATCH_SOURCES, SIGNATURES


REQUIRED_KEYS = {
    "id",
    "technology",
    "category",
    "source",
    "match_type",
    "value_pattern",
    "version_regex",
    "confidence",
}
ALLOWED_MATCH_TYPES = {"contains", "regex", "contains_all"}
ALLOWED_CONFIDENCES = set(CONFIDENCE_RANK)


class SignatureContractTests(unittest.TestCase):
    def test_every_signature_has_required_keys(self) -> None:
        for sig in SIGNATURES:
            missing = REQUIRED_KEYS - set(sig)
            assert not missing, f"signature {sig.get('id')} missing {missing}"

    def test_ids_are_unique(self) -> None:
        ids = [sig["id"] for sig in SIGNATURES]
        assert len(ids) == len(set(ids)), "duplicate signature ids"

    def test_categories_are_in_allowed_set(self) -> None:
        for sig in SIGNATURES:
            assert sig["category"] in CATEGORIES, (
                f"{sig['id']}: bad category {sig['category']}"
            )

    def test_sources_are_in_allowed_set(self) -> None:
        for sig in SIGNATURES:
            assert sig["source"] in MATCH_SOURCES, (
                f"{sig['id']}: bad source {sig['source']}"
            )

    def test_match_types_are_in_allowed_set(self) -> None:
        for sig in SIGNATURES:
            assert sig["match_type"] in ALLOWED_MATCH_TYPES, sig["id"]

    def test_confidences_are_in_allowed_set(self) -> None:
        for sig in SIGNATURES:
            assert sig["confidence"] in ALLOWED_CONFIDENCES, sig["id"]

    def test_version_regexes_compile(self) -> None:
        for sig in SIGNATURES:
            if sig["version_regex"] is not None:
                re.compile(sig["version_regex"])

    def test_contains_all_signatures_have_patterns_list(self) -> None:
        for sig in SIGNATURES:
            if sig["match_type"] == "contains_all":
                assert isinstance(sig["value_pattern"], list), sig["id"]
                assert len(sig["value_pattern"]) >= 2, sig["id"]


class MinimumCoverageTests(unittest.TestCase):
    """The spec's initial-signatures table lists ~20 technologies. The
    library must cover the high-confidence anchor for each major
    framework so live fixtures (Juice Shop = Angular, DVWA = jQuery,
    WebGoat = jQuery+Bootstrap) actually surface a Finding."""

    def _has_tech(self, tech: str) -> bool:
        return any(sig["technology"] == tech for sig in SIGNATURES)

    def test_angular_present(self) -> None:
        assert self._has_tech("Angular")

    def test_react_present(self) -> None:
        assert self._has_tech("React")

    def test_vue_present(self) -> None:
        assert self._has_tech("Vue")

    def test_next_present(self) -> None:
        assert self._has_tech("Next.js")

    def test_jquery_present(self) -> None:
        assert self._has_tech("jQuery")

    def test_bootstrap_present(self) -> None:
        assert self._has_tech("Bootstrap")
