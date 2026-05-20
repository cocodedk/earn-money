"""Tests for the sourceMappingURL comment extractor (stub 1.14 slice 2).

Spec §"Source map reference detection" — supported forms:

JavaScript:
    //# sourceMappingURL=app.js.map
    //@ sourceMappingURL=app.js.map   (legacy)

CSS:
    /*# sourceMappingURL=app.css.map */

Multiple comments may appear in pathological files; tooling
convention puts the canonical one last, so the extractor returns
the last match.
"""
from __future__ import annotations

import unittest

from ..parser import extract_source_mapping_url


class JsSourceMappingUrlTests(unittest.TestCase):
    """JS forms — `//#` and the legacy `//@`."""

    def test_extracts_hash_comment_at_eof(self) -> None:
        body = "console.log('app');\n//# sourceMappingURL=app.js.map\n"
        assert extract_source_mapping_url(body, "javascript") == "app.js.map"

    def test_extracts_at_comment_legacy(self) -> None:
        body = "var x=1;\n//@ sourceMappingURL=legacy.js.map\n"
        assert extract_source_mapping_url(body, "javascript") == "legacy.js.map"

    def test_returns_last_when_multiple_present(self) -> None:
        # Pathological dual-comment file — tooling convention puts
        # the canonical sourceMappingURL last, so that's the one we
        # trust. Earlier ones are usually decoy or in-line strings.
        body = (
            "//# sourceMappingURL=stale.js.map\n"
            "x();\n"
            "//# sourceMappingURL=final.js.map\n"
        )
        assert extract_source_mapping_url(body, "javascript") == "final.js.map"

    def test_strips_trailing_whitespace_around_value(self) -> None:
        body = "//#  sourceMappingURL=  app.js.map   \n"
        assert extract_source_mapping_url(body, "javascript") == "app.js.map"

    def test_absolute_url_value_preserved(self) -> None:
        body = "//# sourceMappingURL=https://cdn.example/x.js.map"
        assert (
            extract_source_mapping_url(body, "javascript")
            == "https://cdn.example/x.js.map"
        )

    def test_inline_data_url_value_preserved_raw(self) -> None:
        # The resolver slice rejects data: URLs; the extractor only
        # returns the raw string so the audit trail is complete.
        body = "//# sourceMappingURL=data:application/json;base64,eyJ2..."
        result = extract_source_mapping_url(body, "javascript")
        assert result is not None and result.startswith("data:application/json")

    def test_returns_none_when_no_comment(self) -> None:
        body = "function x() { return 1; }\n"
        assert extract_source_mapping_url(body, "javascript") is None

    def test_returns_none_for_empty_body(self) -> None:
        assert extract_source_mapping_url("", "javascript") is None

    def test_ignores_css_comment_form_in_js_body(self) -> None:
        # `/*# sourceMappingURL=… */` in a JS body is *technically*
        # valid JS syntax (a block comment) but the spec's JS form
        # is only `//#` / `//@`. Treat the CSS form as unmatched
        # under javascript kind so we don't pick up commented-out
        # source-map directives in JS source.
        body = "/*# sourceMappingURL=oops.js.map */"
        assert extract_source_mapping_url(body, "javascript") is None


class CssSourceMappingUrlTests(unittest.TestCase):
    """CSS form — `/*# sourceMappingURL=… */`."""

    def test_extracts_css_block_comment(self) -> None:
        body = ".x{color:red}\n/*# sourceMappingURL=site.css.map */\n"
        assert extract_source_mapping_url(body, "css") == "site.css.map"

    def test_extracts_css_without_trailing_space(self) -> None:
        # Some bundlers emit `*/` flush against the URL — still valid.
        body = "/*# sourceMappingURL=tight.css.map*/"
        assert extract_source_mapping_url(body, "css") == "tight.css.map"

    def test_css_returns_last_when_multiple_present(self) -> None:
        body = (
            "/*# sourceMappingURL=first.css.map */\n"
            "body { font: 12px; }\n"
            "/*# sourceMappingURL=second.css.map */\n"
        )
        assert extract_source_mapping_url(body, "css") == "second.css.map"

    def test_ignores_js_comment_form_in_css_body(self) -> None:
        # `//# …` is not a CSS comment — must be ignored under the
        # css kind so a malformed bundler emission doesn't get
        # picked up.
        body = "//# sourceMappingURL=oops.css.map"
        assert extract_source_mapping_url(body, "css") is None

    def test_returns_none_when_no_css_comment(self) -> None:
        body = ".btn { color: blue; }\n"
        assert extract_source_mapping_url(body, "css") is None

    def test_rejects_legacy_at_form_for_css(self) -> None:
        # Spec §"Source map reference detection" lists `/*#` for CSS
        # only — the `@` legacy form is JS-only. A `/*@ … */` block
        # in CSS must not be treated as the canonical directive.
        body = "/*@ sourceMappingURL=legacy.css.map */"
        assert extract_source_mapping_url(body, "css") is None
