"""Tests for stub 1.15 HTML bundle-candidate extractor.

Spec §"Extract bundle candidates from HTML" + §"Persistence" (the
discovery_method + script_type enums).
"""
from __future__ import annotations

import unittest

from ..parser import BundleCandidate, extract_bundle_candidates


_BASE = "https://x.example/"


class ScriptSrcTests(unittest.TestCase):
    def test_classic_script_src_yields_candidate(self) -> None:
        html = '<html><body><script src="/assets/app.js"></script></body></html>'
        result = extract_bundle_candidates(html, _BASE)
        assert len(result) == 1
        assert result[0] == BundleCandidate(
            url="https://x.example/assets/app.js",
            discovery_method="script_src",
            script_type="classic",
            same_origin=True,
        )

    def test_module_script_src_marks_module_type(self) -> None:
        html = (
            '<html><body>'
            '<script type="module" src="/static/app.mjs"></script>'
            '</body></html>'
        )
        result = extract_bundle_candidates(html, _BASE)
        assert len(result) == 1
        assert result[0].script_type == "module"
        assert result[0].discovery_method == "module_script_src"

    def test_script_without_src_is_ignored(self) -> None:
        html = '<html><body><script>console.log(1)</script></body></html>'
        assert extract_bundle_candidates(html, _BASE) == []

    def test_external_cdn_marks_not_same_origin(self) -> None:
        html = (
            '<html><body>'
            '<script src="https://cdn.example/lib.js"></script>'
            '</body></html>'
        )
        result = extract_bundle_candidates(html, _BASE)
        assert len(result) == 1
        assert result[0].url == "https://cdn.example/lib.js"
        assert result[0].same_origin is False


class LinkTagDiscoveryTests(unittest.TestCase):
    def test_modulepreload(self) -> None:
        html = (
            '<html><head>'
            '<link rel="modulepreload" href="/static/a.js">'
            '</head></html>'
        )
        result = extract_bundle_candidates(html, _BASE)
        assert len(result) == 1
        assert result[0].discovery_method == "modulepreload"
        assert result[0].script_type == "module"

    def test_preload_as_script(self) -> None:
        html = (
            '<html><head>'
            '<link rel="preload" as="script" href="/static/a.js">'
            '</head></html>'
        )
        result = extract_bundle_candidates(html, _BASE)
        assert len(result) == 1
        assert result[0].discovery_method == "preload_script"
        assert result[0].script_type == "preload"

    def test_preload_non_script_dropped(self) -> None:
        # preload with `as="style"` is not a JS bundle hint.
        html = (
            '<html><head>'
            '<link rel="preload" as="style" href="/static/a.css">'
            '</head></html>'
        )
        assert extract_bundle_candidates(html, _BASE) == []

    def test_prefetch_js_looking_accepted(self) -> None:
        # Spec §"Candidate URL extensions": prefetch entries qualify
        # only when the URL strongly looks like JS (extension match).
        html = (
            '<html><head>'
            '<link rel="prefetch" href="/static/chunk.js">'
            '</head></html>'
        )
        result = extract_bundle_candidates(html, _BASE)
        assert len(result) == 1
        assert result[0].discovery_method == "prefetch"
        assert result[0].script_type == "prefetch"

    def test_prefetch_non_js_dropped(self) -> None:
        # prefetch of a non-JS asset (image, font) must not enter the
        # bundle candidate list.
        html = (
            '<html><head>'
            '<link rel="prefetch" href="/static/hero.png">'
            '</head></html>'
        )
        assert extract_bundle_candidates(html, _BASE) == []

    def test_stylesheet_link_ignored(self) -> None:
        html = '<html><head><link rel="stylesheet" href="/a.css"></head></html>'
        assert extract_bundle_candidates(html, _BASE) == []


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
        # `<link rel="modulepreload">` with no href — drop silently.
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
