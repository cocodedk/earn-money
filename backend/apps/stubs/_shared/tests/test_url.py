"""Tests for the shared URL helpers."""
from __future__ import annotations

import unittest

from ..url import (
    NormalizedUrl,
    OriginVerdict,
    classify_same_origin,
    normalize_url,
    origin,
)


_BASE = "https://example.test/static/app.js"


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


class ClassifySameOriginTests(unittest.TestCase):
    def test_relative_resolves_to_ok(self) -> None:
        verdict = classify_same_origin("app.js.map", _BASE)
        assert verdict == OriginVerdict(
            kind="ok",
            absolute_url="https://example.test/static/app.js.map",
        )

    def test_root_relative_resolves_to_ok(self) -> None:
        verdict = classify_same_origin("/static/app.js.map", _BASE)
        assert verdict.kind == "ok"
        assert verdict.absolute_url == "https://example.test/static/app.js.map"

    def test_absolute_same_origin_ok(self) -> None:
        verdict = classify_same_origin(
            "https://example.test/x", _BASE,
        )
        assert verdict == OriginVerdict(
            kind="ok", absolute_url="https://example.test/x",
        )

    def test_query_and_fragment_preserved(self) -> None:
        verdict = classify_same_origin("app.js.map?v=1#x", _BASE)
        assert verdict.absolute_url == (
            "https://example.test/static/app.js.map?v=1#x"
        )

    def test_unknown_scheme_invalid_scheme(self) -> None:
        verdict = classify_same_origin("ftp://example.test/x", _BASE)
        assert verdict == OriginVerdict(
            kind="invalid_scheme", absolute_url=None,
        )

    def test_javascript_scheme_invalid_scheme(self) -> None:
        # No scheme-prefix-stripping — the helper is a verdict, not a
        # sanitizer. `javascript:` is classified as a non-http scheme.
        verdict = classify_same_origin("javascript:void(0)", _BASE)
        assert verdict.kind == "invalid_scheme"

    def test_different_host_cross_origin(self) -> None:
        verdict = classify_same_origin(
            "https://cdn.other.test/x", _BASE,
        )
        assert verdict == OriginVerdict(
            kind="cross_origin", absolute_url=None,
        )

    def test_different_port_cross_origin(self) -> None:
        verdict = classify_same_origin(
            "https://example.test:8443/x", _BASE,
        )
        assert verdict.kind == "cross_origin"

    def test_scheme_downgrade_cross_origin(self) -> None:
        # http://example.test vs https://example.test → different
        # origins (scheme is part of the origin tuple).
        verdict = classify_same_origin(
            "http://example.test/x", _BASE,
        )
        assert verdict.kind == "cross_origin"


class NormalizeUrlTests(unittest.TestCase):
    def test_relative_resolves_same_origin(self) -> None:
        result = normalize_url("app.js", _BASE)
        assert result == NormalizedUrl(
            url="https://example.test/static/app.js",
            same_origin=True,
        )

    def test_root_relative_resolves_same_origin(self) -> None:
        result = normalize_url("/x/y.js", _BASE)
        assert result.url == "https://example.test/x/y.js"
        assert result.same_origin is True

    def test_cross_origin_keeps_absolute_url(self) -> None:
        # Unlike classify_same_origin, normalize_url preserves the URL
        # on cross-origin — callers want to record CDN bundles too,
        # gated by their own include_cdn_metadata flag.
        result = normalize_url("https://cdn.example/lib.js", _BASE)
        assert result.url == "https://cdn.example/lib.js"
        assert result.same_origin is False

    def test_fragment_stripped(self) -> None:
        result = normalize_url("/a.js#section", _BASE)
        assert result.url == "https://example.test/a.js"

    def test_query_preserved(self) -> None:
        result = normalize_url("/a.js?v=42", _BASE)
        assert result.url == "https://example.test/a.js?v=42"

    def test_invalid_scheme_returns_none(self) -> None:
        result = normalize_url("javascript:alert(1)", _BASE)
        assert result == NormalizedUrl(url=None, same_origin=False)

    def test_data_scheme_returns_none(self) -> None:
        result = normalize_url("data:text/javascript,1", _BASE)
        assert result.url is None
        assert result.same_origin is False

    def test_different_port_marks_cross_origin(self) -> None:
        result = normalize_url("https://example.test:8443/x", _BASE)
        assert result.url == "https://example.test:8443/x"
        assert result.same_origin is False

    def test_scheme_downgrade_marks_cross_origin(self) -> None:
        result = normalize_url("http://example.test/x", _BASE)
        assert result.url == "http://example.test/x"
        assert result.same_origin is False
