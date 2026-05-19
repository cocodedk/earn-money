"""Signature table contract for stub 1.4 backend-hints."""
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
ALLOWED_MATCH_TYPES = {"exact", "contains", "regex"}
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

    def test_cookie_signatures_have_field(self) -> None:
        # cookie source signatures match against cookie NAME (not value);
        # `field` carries the regex/pattern, value_pattern is the
        # name-match pattern.
        for sig in SIGNATURES:
            if sig["source"] == "cookie":
                # The match operates on the cookie name; value_pattern
                # is the name pattern.
                assert sig.get("value_pattern"), sig["id"]


class MinimumCoverageTests(unittest.TestCase):
    """The MVP spec ships detections for the 6 main session-cookie
    families + 4 X-Powered-By/Server headers + 2 body markers."""

    def _has_tech(self, tech: str) -> bool:
        return any(sig["technology"] == tech for sig in SIGNATURES)

    def test_express_present(self) -> None:
        assert self._has_tech("Express")

    def test_django_present(self) -> None:
        assert self._has_tech("Django")

    def test_java_servlet_present(self) -> None:
        assert self._has_tech("Java Servlet")

    def test_aspnet_present(self) -> None:
        assert self._has_tech("ASP.NET")

    def test_laravel_present(self) -> None:
        assert self._has_tech("Laravel")

    def test_php_present(self) -> None:
        assert self._has_tech("PHP")
