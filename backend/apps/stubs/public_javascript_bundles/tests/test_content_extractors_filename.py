"""Tests for stub 1.15 content extractors — filename / extension /
build hints / hash-in-filename.

Spec §4 first three bullets: bounded text scanning on the URL's last
path segment to derive deterministic build hints. No HTTP, no body
parsing — pure string work.
"""
from __future__ import annotations

import unittest

from ..content_extractors import (
    extract_build_hints,
    extract_extension,
    extract_filename,
    extract_hash_in_filename,
)


class ExtractFilenameTests(unittest.TestCase):
    def test_returns_last_path_segment(self) -> None:
        assert extract_filename("https://x.example/assets/app.js") == "app.js"

    def test_strips_query_and_fragment(self) -> None:
        assert extract_filename(
            "https://x.example/assets/main.js?v=1#bookmark"
        ) == "main.js"

    def test_root_path_returns_none(self) -> None:
        assert extract_filename("https://x.example/") is None

    def test_no_path_returns_none(self) -> None:
        assert extract_filename("https://x.example") is None

    def test_nested_path(self) -> None:
        assert extract_filename(
            "https://x.example/static/js/chunk.abc.mjs"
        ) == "chunk.abc.mjs"


class ExtractExtensionTests(unittest.TestCase):
    def test_js(self) -> None:
        assert extract_extension("https://x.example/app.js") == "js"

    def test_mjs(self) -> None:
        assert extract_extension("https://x.example/app.mjs") == "mjs"

    def test_cjs(self) -> None:
        assert extract_extension("https://x.example/app.cjs") == "cjs"

    def test_jsx(self) -> None:
        assert extract_extension("https://x.example/comp.jsx") == "jsx"

    def test_no_extension_returns_none(self) -> None:
        # Bundles served without an extension (e.g. via an API gateway
        # rewrite) — the runner falls back to content-type evidence.
        assert extract_extension("https://x.example/build/bundle") == "none"

    def test_unknown_extension(self) -> None:
        assert extract_extension("https://x.example/style.css") == "unknown"

    def test_case_insensitive(self) -> None:
        assert extract_extension("https://x.example/APP.JS") == "js"


class ExtractBuildHintsTests(unittest.TestCase):
    """Spec §4: 'Filename/build hints: main, runtime, vendor, chunk,
    app, polyfills'."""

    def test_main(self) -> None:
        assert "main" in extract_build_hints("main.js")

    def test_runtime(self) -> None:
        assert "runtime" in extract_build_hints("runtime.js")

    def test_vendor(self) -> None:
        assert "vendor" in extract_build_hints("vendor.bundle.js")

    def test_chunk(self) -> None:
        assert "chunk" in extract_build_hints("chunk-1.js")

    def test_app(self) -> None:
        assert "app" in extract_build_hints("app.js")

    def test_polyfills(self) -> None:
        assert "polyfills" in extract_build_hints("polyfills.legacy.js")

    def test_multiple_hints_in_one_name(self) -> None:
        # webpack convention: `runtime~main.js` bundles both.
        result = extract_build_hints("runtime~main.js")
        assert set(result) == {"runtime", "main"}

    def test_no_known_hint(self) -> None:
        assert extract_build_hints("custom-name.js") == []

    def test_hints_returned_in_canonical_order(self) -> None:
        # Stable order matters for idempotent signature comparison.
        # Canonical: main, runtime, vendor, chunk, app, polyfills.
        result = extract_build_hints("polyfills-app-main.js")
        assert result == ["main", "app", "polyfills"]

    def test_substring_only_match_excluded(self) -> None:
        # `application.js` contains "app" as a SUBSTRING of "application"
        # — but the build hint should match only when "app" appears as
        # a whole token bounded by `.` / `-` / `_` / `~`.
        assert "app" not in extract_build_hints("application.js")


class ExtractHashInFilenameTests(unittest.TestCase):
    """Spec §4: 'hash-like filename segment such as `main.8f31a2.js`,
    `chunk-ABC123.js`, `app.[hash].js`'."""

    def test_hex_hash_detected(self) -> None:
        assert extract_hash_in_filename("main.8f31a2.js") is True

    def test_uppercase_alphanumeric_detected(self) -> None:
        assert extract_hash_in_filename("chunk-ABC123.js") is True

    def test_long_mixed_case_detected(self) -> None:
        assert extract_hash_in_filename("app.aB3xY9z2.js") is True

    def test_short_segment_not_detected(self) -> None:
        # `app.v1.js` — a 2-char segment is too short to be a hash.
        assert extract_hash_in_filename("app.v1.js") is False

    def test_pure_word_segment_not_detected(self) -> None:
        # No digit in the segment; spec example needs alphanumeric mix.
        assert extract_hash_in_filename("vendor.bundle.js") is False

    def test_no_hash_in_simple_filename(self) -> None:
        assert extract_hash_in_filename("main.js") is False

    def test_template_placeholder_detected(self) -> None:
        # `app.[hash].js` — the literal `[hash]` placeholder used in
        # framework manifests is preserved as a deterministic marker.
        assert extract_hash_in_filename("app.[hash].js") is True
