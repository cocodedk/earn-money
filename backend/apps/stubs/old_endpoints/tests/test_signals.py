"""Tests for stub 1.9 signal detectors."""
from __future__ import annotations

import unittest

from ..signals import (
    body_has_deprecation_marker,
    header_deprecation_evidence,
    path_has_stale_token_segment,
)


class HeaderDeprecationEvidenceTests(unittest.TestCase):
    def test_deprecation_header_detected(self) -> None:
        # RFC 8594: presence of `Deprecation` header is the canonical
        # explicit deprecation signal. Value `true` is RFC-suggested
        # but any truthy presence counts.
        ev = header_deprecation_evidence({"Deprecation": "true"})
        assert "header:Deprecation" in ev

    def test_sunset_header_detected(self) -> None:
        ev = header_deprecation_evidence(
            {"Sunset": "Wed, 31 Dec 2025 23:59:59 GMT"},
        )
        assert "header:Sunset" in ev

    def test_warning_299_detected(self) -> None:
        # RFC 7234 §5.5: warn-code 299 is "Miscellaneous Persistent
        # Warning". Common for vendor deprecation messaging.
        ev = header_deprecation_evidence(
            {"Warning": '299 - "Deprecated API, use /api/v2/"'},
        )
        assert "header:Warning:299" in ev

    def test_warning_other_code_not_detected(self) -> None:
        # Warn-code 199 ("Miscellaneous Warning") is informational, not
        # deprecation-bound. Must not surface as deprecation evidence.
        ev = header_deprecation_evidence(
            {"Warning": '199 - "Miscellaneous warning"'},
        )
        assert ev == []

    def test_link_deprecation_rel_detected(self) -> None:
        ev = header_deprecation_evidence(
            {"Link": '</api/v2/users>; rel="deprecation"'},
        )
        assert 'header:Link:rel=deprecation' in ev

    def test_link_sunset_rel_detected(self) -> None:
        ev = header_deprecation_evidence(
            {"Link": '</api/v2/users>; rel="sunset"'},
        )
        assert 'header:Link:rel=sunset' in ev

    def test_link_other_rel_not_detected(self) -> None:
        # `rel="next"` and friends are pagination/navigation, not
        # deprecation. Must not false-positive.
        ev = header_deprecation_evidence(
            {"Link": '</api/v1/users?page=2>; rel="next"'},
        )
        assert ev == []

    def test_case_insensitive_header_name(self) -> None:
        # HTTP headers are case-insensitive on the wire; httpx normalises
        # but downstream code may not — be robust.
        ev = header_deprecation_evidence({"deprecation": "true"})
        assert "header:Deprecation" in ev

    def test_empty_headers_yields_no_evidence(self) -> None:
        assert header_deprecation_evidence({}) == []


class BodyDeprecationMarkerTests(unittest.TestCase):
    def test_deprecated_word_detected(self) -> None:
        assert body_has_deprecation_marker(
            "<p>This endpoint is deprecated.</p>",
        )

    def test_sunset_word_detected(self) -> None:
        assert body_has_deprecation_marker("Sunset: 2025-12-31")

    def test_legacy_api_phrase_detected(self) -> None:
        assert body_has_deprecation_marker("legacy api")

    def test_end_of_life_hyphenated_detected(self) -> None:
        assert body_has_deprecation_marker(
            "Notice: end-of-life on 2025-12-31",
        )

    def test_use_the_new_api_detected(self) -> None:
        assert body_has_deprecation_marker(
            "Please use the new api going forward.",
        )

    def test_case_insensitive(self) -> None:
        assert body_has_deprecation_marker("DEPRECATED ENDPOINT")

    def test_innocuous_body_not_flagged(self) -> None:
        # `oldfield` is a substring of "old" — must not false-positive
        # since "old" alone isn't a body marker (it's a path-token).
        assert not body_has_deprecation_marker(
            "<form><input name='oldfield'></form>",
        )

    def test_empty_body_not_flagged(self) -> None:
        assert not body_has_deprecation_marker("")


class PathStaleTokenSegmentTests(unittest.TestCase):
    def test_v1_segment_matches(self) -> None:
        assert path_has_stale_token_segment("/api/v1/users") == "v1"

    def test_legacy_segment_matches(self) -> None:
        assert path_has_stale_token_segment("/legacy/login") == "legacy"

    def test_old_inside_word_does_not_match(self) -> None:
        # `/products/gold` contains "old" as a SUBSTRING of "gold" but
        # not as a path segment. Spec §Token matching rules: segments
        # only. Must return None.
        assert path_has_stale_token_segment("/products/gold") is None

    def test_v1_in_asset_filename_does_not_match(self) -> None:
        # `/assets/app.v1.js` — `v1` appears as a dot-separated
        # version in a filename, not as a path segment. Must reject.
        assert path_has_stale_token_segment("/assets/app.v1.js") is None

    def test_trailing_slash_irrelevant(self) -> None:
        assert path_has_stale_token_segment("/legacy/") == "legacy"
        assert path_has_stale_token_segment("/api/v1/") == "v1"

    def test_case_insensitive(self) -> None:
        # Server-controlled paths are case-sensitive but legacy systems
        # often advertise `/LEGACY/` — treat the comparison as
        # case-folded so we don't miss them.
        assert path_has_stale_token_segment("/LEGACY/login") == "legacy"

    def test_first_stale_segment_returned(self) -> None:
        # When multiple stale segments are present (rare), return the
        # FIRST one for stable evidence ordering.
        assert (
            path_has_stale_token_segment("/legacy/v1/users") == "legacy"
        )

    def test_root_path_returns_none(self) -> None:
        assert path_has_stale_token_segment("/") is None
        assert path_has_stale_token_segment("") is None
