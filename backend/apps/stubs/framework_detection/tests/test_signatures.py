"""The 9 baseline signatures defined in cookbook 1.1 §Detection logic."""
from __future__ import annotations

import unittest

from ..signatures import SIGNATURES


class SignatureLibraryTests(unittest.TestCase):
    def test_unique_ids(self) -> None:
        ids = [sig["id"] for sig in SIGNATURES]
        assert len(ids) == len(set(ids))

    def test_each_has_required_keys(self) -> None:
        required = {"id", "technology", "category", "source", "field",
                    "match_type", "confidence"}
        for sig in SIGNATURES:
            assert required.issubset(sig.keys()), sig["id"]
            if sig["match_type"] == "contains_all":
                assert "patterns" in sig
            else:
                assert "pattern" in sig

    def test_confidence_is_in_known_enum(self) -> None:
        for sig in SIGNATURES:
            assert sig["confidence"] in {"low", "medium", "high"}, sig["id"]

    def test_category_is_in_known_set(self) -> None:
        # The spec uses these four categories — adding a new one means
        # updating both the spec and this test together.
        allowed = {"runtime", "frontend_framework",
                   "backend_framework", "known_product"}
        for sig in SIGNATURES:
            assert sig["category"] in allowed, sig["id"]
