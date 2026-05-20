"""Tests for stub 1.15 — importmap discovery + URL normalization.

Spec §"Extract bundle candidates from HTML" (importmap branch) and
§"URL normalization" (dedupe, fragment-stripping, query-preserving,
non-fetchable-scheme rejection).
"""
from __future__ import annotations

import unittest

from ..parser import extract_bundle_candidates


_BASE = "https://x.example/"


class ImportMapTests(unittest.TestCase):
    def test_importmap_extracts_imports_and_scopes(self) -> None:
        html = (
            '<html><head>'
            '<script type="importmap">'
            '{"imports": {"lodash": "/vendor/lodash.js"},'
            ' "scopes": {"/admin/": {"helper": "/admin/h.js"}}}'
            "</script></head></html>"
        )
        result = extract_bundle_candidates(html, _BASE)
        urls = {c.url for c in result}
        assert "https://x.example/vendor/lodash.js" in urls
        assert "https://x.example/admin/h.js" in urls
        for candidate in result:
            assert candidate.discovery_method == "importmap"
            assert candidate.script_type == "importmap"

    def test_importmap_invalid_json_is_skipped(self) -> None:
        # Malformed importmap body must not crash the parser.
        html = (
            '<html><head>'
            '<script type="importmap">not-json</script>'
            '</head></html>'
        )
        assert extract_bundle_candidates(html, _BASE) == []

    def test_importmap_scopes_only_no_imports(self) -> None:
        # importmap with scopes but no imports — exercises the
        # `imports is None` branch in the JSON walker.
        html = (
            '<html><head><script type="importmap">'
            '{"scopes": {"/x/": {"k": "/x/v.js"}}}'
            "</script></head></html>"
        )
        result = extract_bundle_candidates(html, _BASE)
        assert len(result) == 1
        assert result[0].url == "https://x.example/x/v.js"

    def test_importmap_non_dict_root_is_skipped(self) -> None:
        # importmap whose JSON is an array, not an object — JSON
        # parses but the shape is wrong, must yield nothing.
        html = (
            '<html><head><script type="importmap">[1,2,3]</script></head></html>'
        )
        assert extract_bundle_candidates(html, _BASE) == []

    def test_importmap_imports_only_no_scopes(self) -> None:
        # imports present, scopes key absent — exercises the
        # `scopes is not dict` skip branch.
        html = (
            '<html><head><script type="importmap">'
            '{"imports": {"k": "/v.js"}}'
            "</script></head></html>"
        )
        result = extract_bundle_candidates(html, _BASE)
        assert len(result) == 1
        assert result[0].url == "https://x.example/v.js"

    def test_importmap_scope_value_not_dict_skipped(self) -> None:
        # scopes itself is a dict, but a scope's value is a string —
        # tolerate the malformed entry without crashing.
        html = (
            '<html><head><script type="importmap">'
            '{"scopes": {"/a/": "wrong-shape", "/b/": {"k": "/b/v.js"}}}'
            "</script></head></html>"
        )
        result = extract_bundle_candidates(html, _BASE)
        assert len(result) == 1
        assert result[0].url == "https://x.example/b/v.js"


class NormalizationTests(unittest.TestCase):
    def test_dedupes_by_normalized_url(self) -> None:
        html = (
            '<html><body>'
            '<script src="/assets/app.js"></script>'
            '<script src="/assets/app.js"></script>'
            "</body></html>"
        )
        assert len(extract_bundle_candidates(html, _BASE)) == 1

    def test_fragment_stripped(self) -> None:
        html = '<html><body><script src="/a.js#bookmark"></script></body></html>'
        assert extract_bundle_candidates(html, _BASE)[0].url == (
            "https://x.example/a.js"
        )

    def test_query_string_preserved(self) -> None:
        # Per spec: query strings may select versioned assets.
        html = '<html><body><script src="/a.js?v=123"></script></body></html>'
        assert extract_bundle_candidates(html, _BASE)[0].url == (
            "https://x.example/a.js?v=123"
        )

    def test_empty_html_returns_empty(self) -> None:
        assert extract_bundle_candidates("", _BASE) == []

    def test_link_without_href_is_ignored(self) -> None:
        html = '<html><head><link rel="modulepreload"></head></html>'
        assert extract_bundle_candidates(html, _BASE) == []

    def test_javascript_scheme_dropped(self) -> None:
        # `javascript:` and `data:` schemes are non-fetchable; the
        # parser must skip them rather than feed them downstream.
        html = (
            '<html><body>'
            '<script src="javascript:alert(1)"></script>'
            '<script src="data:text/javascript,1"></script>'
            "</body></html>"
        )
        assert extract_bundle_candidates(html, _BASE) == []
