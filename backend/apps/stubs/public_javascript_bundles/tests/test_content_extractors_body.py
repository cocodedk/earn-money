"""Tests for stub 1.15 content extractors — minified marker + source-
map reference.

Spec §4 'minified marker' and 'Source-map reference: trailing or
inline sourceMappingURL= comment'.
"""
from __future__ import annotations

import unittest

from ..content_extractors import (
    extract_minified_marker,
    extract_source_map_url,
)


class ExtractMinifiedMarkerTests(unittest.TestCase):
    def test_unminified_multiline_body_is_false(self) -> None:
        body = (
            "function greet(name) {\n"
            "    console.log('hello ' + name);\n"
            "}\n"
            "greet('world');\n"
        )
        assert extract_minified_marker(body) is False

    def test_compact_single_line_long_body_is_true(self) -> None:
        # 1500-char single line with semicolons but no newlines — the
        # canonical minified shape.
        body = "var a=1;" * 200  # 1600 chars on one line
        assert extract_minified_marker(body) is True

    def test_empty_body_is_false(self) -> None:
        assert extract_minified_marker("") is False

    def test_short_body_is_false(self) -> None:
        # Below the size floor — heuristic abstains, returns False.
        assert extract_minified_marker("var a=1;") is False

    def test_two_long_lines_still_minified(self) -> None:
        # webpack-style: each chunk is one line; module map is another.
        # Two extremely long lines still count as minified.
        body = ("a" * 600 + "\n") * 2
        assert extract_minified_marker(body) is True

    def test_pretty_printed_with_long_strings_is_false(self) -> None:
        # A readable file containing a single long string literal
        # shouldn't trip the heuristic — most lines are short.
        body = "\n".join(["line " + str(i) for i in range(100)])
        body += "\nvar URL = '" + "x" * 800 + "';\n"
        assert extract_minified_marker(body) is False


class ExtractSourceMapUrlTests(unittest.TestCase):
    """Spec §4 'Source-map reference'. Mirror of source_maps stub's
    JS-comment extractor; CSS form is not in scope here (only JS
    bundles are fetched by 1.15)."""

    def test_modern_directive_extracted(self) -> None:
        body = "function x(){}\n//# sourceMappingURL=app.js.map\n"
        assert extract_source_map_url(body) == "app.js.map"

    def test_legacy_at_directive_extracted(self) -> None:
        body = "function x(){}\n//@ sourceMappingURL=legacy.map\n"
        assert extract_source_map_url(body) == "legacy.map"

    def test_no_directive_returns_none(self) -> None:
        assert extract_source_map_url("function x(){}\n") is None

    def test_empty_body_returns_none(self) -> None:
        assert extract_source_map_url("") is None

    def test_last_directive_wins(self) -> None:
        # Bundler convention: canonical comment appears last; earlier
        # //# lines are decoys (debug leftovers, fixture comments).
        body = (
            "//# sourceMappingURL=stale.map\n"
            "var x=1;\n"
            "//# sourceMappingURL=current.map\n"
        )
        assert extract_source_map_url(body) == "current.map"

    def test_trailing_whitespace_stripped(self) -> None:
        body = "x;\n//# sourceMappingURL=app.js.map   \n"
        assert extract_source_map_url(body) == "app.js.map"

    def test_absolute_url_value_preserved(self) -> None:
        body = "x;\n//# sourceMappingURL=https://cdn.example/app.js.map\n"
        assert extract_source_map_url(body) == "https://cdn.example/app.js.map"

    def test_data_url_value_preserved(self) -> None:
        # Inline source maps come as `data:application/json;base64,...`.
        # The extractor is content-blind — record the raw value, let
        # a later resolver decide.
        body = "x;\n//# sourceMappingURL=data:application/json;base64,e30=\n"
        assert extract_source_map_url(body) == (
            "data:application/json;base64,e30="
        )

    def test_css_form_in_js_body_ignored(self) -> None:
        # /*# sourceMappingURL=... */ is the CSS form. A bundler that
        # emits it inside JS is malformed — must not be returned.
        body = "x;\n/*# sourceMappingURL=stylish.map */\n"
        assert extract_source_map_url(body) is None
