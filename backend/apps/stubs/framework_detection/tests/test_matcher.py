"""Matcher branches — every match_type and every supported (source, field)."""
from __future__ import annotations

import unittest

from ..matcher import extract, matches


class ExtractTests(unittest.TestCase):
    def test_cookie_name_extraction(self) -> None:
        bundle = {"cookies": [{"name": "PHPSESSID", "value": "abc"}]}
        assert extract(bundle, "cookie", "name") == ["PHPSESSID"]

    def test_cookie_skips_when_field_missing(self) -> None:
        bundle = {"cookies": [{"value": "abc"}]}  # no 'name' key
        assert extract(bundle, "cookie", "name") == []

    def test_header_extraction(self) -> None:
        bundle = {"headers": {"X-Powered-By": "PHP/8.2.0"}}
        assert extract(bundle, "header", "X-Powered-By") == ["PHP/8.2.0"]

    def test_header_missing_returns_empty_string(self) -> None:
        bundle = {"headers": {}}
        assert extract(bundle, "header", "X-Powered-By") == [""]

    def test_html_body_extraction(self) -> None:
        bundle = {"html_body": "<html>Hello</html>"}
        assert extract(bundle, "html", "body") == ["<html>Hello</html>"]

    def test_html_script_names_extraction(self) -> None:
        bundle = {"script_names": ["main.js", "polyfills.js"]}
        assert extract(bundle, "html", "script_names") == ["main.js", "polyfills.js"]

    def test_unknown_source_returns_empty(self) -> None:
        assert extract({"headers": {"X": "Y"}}, "unknown-source", "x") == []

    def test_html_unknown_field_returns_empty(self) -> None:
        assert extract({"html_body": "x"}, "html", "not_a_real_field") == []


class MatchesTests(unittest.TestCase):
    def _sig(self, **overrides):
        base = {
            "id": "test",
            "technology": "PHP",
            "category": "runtime",
            "source": "cookie",
            "field": "name",
            "match_type": "equals",
            "pattern": "PHPSESSID",
            "confidence": "high",
        }
        base.update(overrides)
        return base

    def test_equals_match(self) -> None:
        sig = self._sig(match_type="equals", pattern="PHPSESSID")
        assert matches(sig, {"cookies": [{"name": "PHPSESSID"}]}) is True

    def test_equals_no_match(self) -> None:
        sig = self._sig(match_type="equals", pattern="PHPSESSID")
        assert matches(sig, {"cookies": [{"name": "JSESSIONID"}]}) is False

    def test_contains_match_in_header(self) -> None:
        sig = self._sig(
            source="header", field="X-Powered-By",
            match_type="contains", pattern="Express",
        )
        assert matches(sig, {"headers": {"X-Powered-By": "Express 4.18"}}) is True

    def test_contains_skips_empty_values(self) -> None:
        sig = self._sig(source="header", field="X-Powered-By",
                        match_type="contains", pattern="Express")
        assert matches(sig, {"headers": {"X-Powered-By": ""}}) is False

    def test_contains_all_match(self) -> None:
        sig = self._sig(
            source="html", field="script_names",
            match_type="contains_all",
            patterns=["runtime", "polyfills", "main"],
        )
        bundle = {"script_names": ["runtime.js", "polyfills.123.js", "main.456.js"]}
        assert matches(sig, bundle) is True

    def test_contains_all_partial_no_match(self) -> None:
        sig = self._sig(
            source="html", field="script_names",
            match_type="contains_all",
            patterns=["runtime", "polyfills", "main"],
        )
        bundle = {"script_names": ["runtime.js", "polyfills.js"]}  # missing main
        assert matches(sig, bundle) is False

    def test_no_evidence_for_source_returns_false(self) -> None:
        """A signature whose source isn't represented in the bundle
        cleanly reports no match — no crash."""
        sig = self._sig(source="cookie", field="name")
        assert matches(sig, {}) is False  # empty bundle
