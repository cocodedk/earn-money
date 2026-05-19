"""Tests for the map URL resolver (stub 1.14 slice 3).

Spec §"Source map reference detection" — accepted reference types:
relative, root-relative, absolute same-origin. Rejected: data:,
javascript:, file:, ftp:, cross-origin, malformed.

`data:` inline maps get their own kind so the runner can emit a
candidate finding with map_reference_type="inline_data_url" per
spec without decoding the body.
"""
from __future__ import annotations

import unittest

from ..resolver import ResolvedMapUrl, resolve_map_url


_ASSET = "https://example.test/static/app.js"


class AcceptedReferenceTypesTests(unittest.TestCase):
    def test_relative_url_resolves_against_asset_dir(self) -> None:
        result = resolve_map_url("app.js.map", _ASSET)
        assert result == ResolvedMapUrl(
            kind="ok", absolute_url="https://example.test/static/app.js.map",
        )

    def test_root_relative_url_resolves_against_origin(self) -> None:
        result = resolve_map_url("/static/app.js.map", _ASSET)
        assert result == ResolvedMapUrl(
            kind="ok", absolute_url="https://example.test/static/app.js.map",
        )

    def test_absolute_same_origin_url_accepted(self) -> None:
        result = resolve_map_url(
            "https://example.test/static/app.js.map", _ASSET,
        )
        assert result.kind == "ok"
        assert result.absolute_url == "https://example.test/static/app.js.map"

    def test_query_string_preserved(self) -> None:
        result = resolve_map_url("app.js.map?v=1", _ASSET)
        assert result.kind == "ok"
        assert result.absolute_url == "https://example.test/static/app.js.map?v=1"

    def test_fragment_preserved(self) -> None:
        result = resolve_map_url("app.js.map#section", _ASSET)
        assert result.kind == "ok"
        assert result.absolute_url == "https://example.test/static/app.js.map#section"

    def test_asset_url_without_path_resolves_to_root(self) -> None:
        # Asset at the origin root — relative resolves to the same dir
        # (origin root) per urljoin RFC 3986 semantics.
        result = resolve_map_url("app.js.map", "https://example.test/")
        assert result.absolute_url == "https://example.test/app.js.map"


class RejectedReferenceTypesTests(unittest.TestCase):
    def test_inline_data_url_classified_separately(self) -> None:
        # data: maps get their own kind — the runner creates a
        # candidate finding with map_reference_type=inline_data_url
        # and never decodes the body.
        result = resolve_map_url(
            "data:application/json;base64,eyJ2ZXJzaW9uIjozfQ==", _ASSET,
        )
        assert result == ResolvedMapUrl(kind="inline_data_url", absolute_url=None)

    def test_javascript_url_rejected(self) -> None:
        result = resolve_map_url("javascript:void(0)", _ASSET)
        assert result == ResolvedMapUrl(kind="invalid", absolute_url=None)

    def test_file_url_rejected(self) -> None:
        result = resolve_map_url("file:///etc/passwd", _ASSET)
        assert result == ResolvedMapUrl(kind="invalid", absolute_url=None)

    def test_ftp_url_rejected(self) -> None:
        result = resolve_map_url("ftp://example.test/x.map", _ASSET)
        assert result == ResolvedMapUrl(kind="invalid", absolute_url=None)

    def test_blob_url_rejected(self) -> None:
        result = resolve_map_url(
            "blob:https://example.test/abc-def", _ASSET,
        )
        assert result == ResolvedMapUrl(kind="invalid", absolute_url=None)

    def test_mailto_url_rejected(self) -> None:
        result = resolve_map_url("mailto:x@y.test", _ASSET)
        assert result == ResolvedMapUrl(kind="invalid", absolute_url=None)

    def test_cross_origin_https_rejected_as_cross_origin(self) -> None:
        # Different host with valid scheme — distinct kind from the
        # malformed/bad-scheme rejections so the runner can emit
        # diagnostics that match the spec's "cross-origin" category.
        result = resolve_map_url(
            "https://cdn.other.test/static/app.js.map", _ASSET,
        )
        assert result == ResolvedMapUrl(kind="cross_origin", absolute_url=None)

    def test_cross_origin_different_port_rejected(self) -> None:
        result = resolve_map_url(
            "https://example.test:8443/app.js.map", _ASSET,
        )
        assert result == ResolvedMapUrl(kind="cross_origin", absolute_url=None)

    def test_cross_origin_scheme_mismatch_rejected(self) -> None:
        # http://example.test vs https://example.test → different
        # origins per RFC 6454 (scheme is part of the origin tuple).
        result = resolve_map_url(
            "http://example.test/static/app.js.map", _ASSET,
        )
        assert result == ResolvedMapUrl(kind="cross_origin", absolute_url=None)

    def test_empty_raw_value_rejected(self) -> None:
        result = resolve_map_url("", _ASSET)
        assert result == ResolvedMapUrl(kind="invalid", absolute_url=None)

    def test_whitespace_only_rejected(self) -> None:
        result = resolve_map_url("   ", _ASSET)
        assert result == ResolvedMapUrl(kind="invalid", absolute_url=None)

    def test_garbage_with_unknown_scheme_rejected(self) -> None:
        # The resolver doesn't strict-validate URL syntax — urljoin is
        # liberal. The actual filter is the scheme allowlist after
        # resolution. A bare unknown scheme is the deterministic
        # malformed-style input we get a rejection on.
        result = resolve_map_url("weird-scheme:payload", _ASSET)
        assert result == ResolvedMapUrl(kind="invalid", absolute_url=None)
