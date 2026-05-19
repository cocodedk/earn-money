"""Tests for the shared URL helpers."""
from __future__ import annotations

import unittest

from ..url import origin


class OriginTests(unittest.TestCase):
    def test_strips_path(self) -> None:
        assert origin("https://x.example/foo/bar") == "https://x.example"

    def test_preserves_port(self) -> None:
        assert origin("http://x.example:8080/foo") == "http://x.example:8080"

    def test_scheme_lowercased_per_urlsplit(self) -> None:
        # urlsplit normalises scheme to lowercase; downstream same-origin
        # comparisons rely on case-insensitive equivalence between URLs
        # with mixed scheme casing.
        assert origin("HTTPS://x.example/") == "https://x.example"
