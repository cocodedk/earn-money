"""Tests for stub 1.15 framework-hint extractor.

Spec §4 'Framework hints from deterministic strings' — substring
search of the bundle body against a closed signature table; each
match yields one FrameworkHint(name, matched_pattern, confidence).
Multiple matching patterns from the same framework all surface so
the runner can record the corroborating evidence.
"""
from __future__ import annotations

import unittest

from ..framework_hints import (
    FrameworkHint,
    extract_framework_hints,
)


def _names(body: str) -> set[str]:
    return {hint.name for hint in extract_framework_hints(body)}


def _patterns(body: str, name: str) -> set[str]:
    return {h.matched_pattern for h in extract_framework_hints(body)
            if h.name == name}


class ReactTests(unittest.TestCase):
    def test_devtools_hook_is_high_confidence(self) -> None:
        body = "if(__REACT_DEVTOOLS_GLOBAL_HOOK__){...}"
        hints = extract_framework_hints(body)
        match = next(h for h in hints if h.matched_pattern.endswith("HOOK__"))
        assert match.name == "react"
        assert match.confidence == "high"

    def test_data_reactroot_high_confidence(self) -> None:
        assert any(
            h.matched_pattern == "data-reactroot" and h.confidence == "high"
            for h in extract_framework_hints("<div data-reactroot></div>")
        )

    def test_react_dom_medium_confidence(self) -> None:
        body = "import x from 'react-dom';"
        match = next(
            h for h in extract_framework_hints(body)
            if h.matched_pattern == "react-dom"
        )
        assert match.confidence == "medium"

    def test_bare_react_low_confidence(self) -> None:
        # The substring "react" alone is ambiguous (could be a
        # variable name, a doc string) — low-confidence signal.
        match = next(
            h for h in extract_framework_hints("var react = 1;")
            if h.matched_pattern == "react"
        )
        assert match.confidence == "low"


class VueTests(unittest.TestCase):
    def test_devtools_hook_high(self) -> None:
        body = "window.__VUE_DEVTOOLS_GLOBAL_HOOK__=x;"
        assert "vue" in _names(body)

    def test_vue_global_high(self) -> None:
        match = next(
            h for h in extract_framework_hints("var __VUE__=1;")
            if h.matched_pattern == "__VUE__"
        )
        assert match.confidence == "high"

    def test_create_app_medium(self) -> None:
        match = next(
            h for h in extract_framework_hints("createApp(App).mount('#x')")
            if h.matched_pattern == "createApp("
        )
        assert match.confidence == "medium"


class AngularTests(unittest.TestCase):
    def test_ng_version_high(self) -> None:
        assert "angular" in _names('<app ng-version="17.0.0"></app>')

    def test_zone_js_high(self) -> None:
        assert "angular" in _names("require('zone.js/dist/zone');")

    def test_polyfills_low_confidence(self) -> None:
        match = next(
            h for h in extract_framework_hints("// polyfills loader")
            if h.matched_pattern == "polyfills"
        )
        assert match.name == "angular"
        assert match.confidence == "low"


class SvelteTests(unittest.TestCase):
    def test_svelte_global_high(self) -> None:
        assert "svelte" in _names("window.__svelte={};")

    def test_sveltekit_path_high(self) -> None:
        body = 'import "/_app/immutable/chunks/x.js"'
        match = next(
            h for h in extract_framework_hints(body)
            if h.matched_pattern == "/_app/immutable/"
        )
        assert match.confidence == "high"


class NextJsTests(unittest.TestCase):
    def test_next_data_high(self) -> None:
        assert "nextjs" in _names('<script id="__NEXT_DATA__">{}</script>')

    def test_next_f_high(self) -> None:
        assert "nextjs" in _names("self.__next_f=self.__next_f||[];")

    def test_next_static_path_high(self) -> None:
        assert "nextjs" in _names('import "/_next/static/chunks/main.js"')


class NuxtTests(unittest.TestCase):
    def test_nuxt_global_high(self) -> None:
        assert "nuxt" in _names("window.__NUXT__={};")

    def test_nuxt_path_high(self) -> None:
        assert "nuxt" in _names('"/_nuxt/entry.abc.js"')


class ViteTests(unittest.TestCase):
    def test_import_meta_env_high(self) -> None:
        assert "vite" in _names("var mode = import.meta.env.MODE;")

    def test_at_vite_path_high(self) -> None:
        assert "vite" in _names('import "/@vite/client";')


class WebpackTests(unittest.TestCase):
    def test_webpack_require_high(self) -> None:
        body = "var __webpack_require__ = function(){...};"
        match = next(
            h for h in extract_framework_hints(body)
            if h.matched_pattern == "__webpack_require__"
        )
        assert match.confidence == "high"

    def test_webpack_chunk_high(self) -> None:
        assert "webpack" in _names("self.webpackChunk_app=[];")


class RemixTests(unittest.TestCase):
    def test_remix_context_high(self) -> None:
        assert "remix" in _names("window.__remixContext={};")

    def test_build_manifest_medium(self) -> None:
        match = next(
            h for h in extract_framework_hints("var buildManifest={};")
            if h.matched_pattern == "buildManifest"
        )
        assert match.confidence == "medium"


class GeneralTests(unittest.TestCase):
    def test_empty_body_returns_empty(self) -> None:
        assert extract_framework_hints("") == []

    def test_no_match_returns_empty(self) -> None:
        assert extract_framework_hints("plain text with no marker") == []

    def test_multi_framework_body(self) -> None:
        # A real-world bundle may legitimately ship both React and
        # webpack runtime; the extractor surfaces both.
        body = (
            "var __webpack_require__=1;"
            "var __REACT_DEVTOOLS_GLOBAL_HOOK__=x;"
        )
        names = _names(body)
        assert "react" in names and "webpack" in names

    def test_returns_namedtuple(self) -> None:
        hints = extract_framework_hints("__NEXT_DATA__")
        assert isinstance(hints[0], FrameworkHint)
        assert hints[0].name == "nextjs"

    def test_multiple_react_patterns_all_surface(self) -> None:
        # When a bundle carries several patterns from the same
        # framework, EACH matched pattern lands as its own hint so
        # the runner records the corroborating evidence.
        body = (
            "<div data-reactroot></div>"
            "var __REACT_DEVTOOLS_GLOBAL_HOOK__=1;"
            "import 'react-dom';"
        )
        assert _patterns(body, "react") == {
            "data-reactroot",
            "__REACT_DEVTOOLS_GLOBAL_HOOK__",
            "react-dom",
            "react",  # substring of react-dom
        }
