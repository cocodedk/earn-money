"""Signature table contract for stub 1.2 server-headers."""
from __future__ import annotations

import re
import unittest

from apps.findings.confidence import CONFIDENCE_RANK

from ..signatures import SIGNATURES, TECHNOLOGY_CATEGORIES


REQUIRED_KEYS = {
    "id",
    "header_name",
    "value_pattern",
    "match_type",
    "technology",
    "technology_category",
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

    def test_header_names_are_lowercase(self) -> None:
        for sig in SIGNATURES:
            assert sig["header_name"] == sig["header_name"].lower(), (
                f"{sig['id']}: header_name must be normalized lowercase"
            )

    def test_match_types_are_in_allowed_set(self) -> None:
        for sig in SIGNATURES:
            assert sig["match_type"] in ALLOWED_MATCH_TYPES, sig["id"]

    def test_confidences_are_in_allowed_set(self) -> None:
        for sig in SIGNATURES:
            assert sig["confidence"] in ALLOWED_CONFIDENCES, sig["id"]

    def test_technology_categories_are_in_allowed_set(self) -> None:
        for sig in SIGNATURES:
            assert sig["technology_category"] in TECHNOLOGY_CATEGORIES, (
                f"{sig['id']} has category {sig['technology_category']}"
            )

    def test_version_regexes_compile(self) -> None:
        for sig in SIGNATURES:
            if sig["version_regex"] is not None:
                re.compile(sig["version_regex"])


class MinimumSignatureCoverageTests(unittest.TestCase):
    """Spot-check the spec's minimum signature set is present."""

    def _has_tech(self, tech: str) -> bool:
        return any(sig["technology"] == tech for sig in SIGNATURES)

    def test_nginx_present(self) -> None:
        assert self._has_tech("nginx")

    def test_apache_present(self) -> None:
        assert self._has_tech("apache_httpd")

    def test_express_present(self) -> None:
        assert self._has_tech("express")

    def test_cloudflare_present(self) -> None:
        assert self._has_tech("cloudflare")

    def test_cloudfront_present(self) -> None:
        assert self._has_tech("aws_cloudfront")
