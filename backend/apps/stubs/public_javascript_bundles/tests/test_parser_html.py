"""Tests for stub 1.15 — HTML script + link discovery.

Spec §"Extract bundle candidates from HTML": the
``<script src>``, ``<script type="module" src>``, ``<link
rel="modulepreload">``, ``<link rel="preload" as="script">`` and
``<link rel="prefetch">`` discovery methods.
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
        html = (
            '<html><head>'
            '<link rel="prefetch" href="/static/hero.png">'
            '</head></html>'
        )
        assert extract_bundle_candidates(html, _BASE) == []

    def test_stylesheet_link_ignored(self) -> None:
        html = '<html><head><link rel="stylesheet" href="/a.css"></head></html>'
        assert extract_bundle_candidates(html, _BASE) == []
