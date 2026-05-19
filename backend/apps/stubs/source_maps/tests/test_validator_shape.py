"""Shape acceptance + rejection tests for the Source Map v3 validator.

Spec §"Source map fetch" requires the body to parse as JSON with
`version` plus at least one of `sources`, `sections`, or `mappings`.
Anything else (empty, non-JSON, JSON array/scalar, missing keys)
returns None so the runner downgrades to a candidate finding.
"""
from __future__ import annotations

import json
import unittest

from ..validator import parse_source_map
from ._validator_factories import minimal_v3


class ShapeAcceptanceTests(unittest.TestCase):
    def test_minimal_v3_parses(self) -> None:
        meta = parse_source_map(json.dumps(minimal_v3()))
        assert meta is not None
        assert meta.version == 3
        assert meta.sources_count == 1
        assert meta.has_sources_content is True
        assert meta.sources_content_count == 1

    def test_accepts_map_with_only_sections(self) -> None:
        # Spec §"Source map fetch": valid maps need version + at least
        # one of sources/sections/mappings. `sections` alone is enough.
        body = json.dumps({"version": 3, "sections": []})
        meta = parse_source_map(body)
        assert meta is not None
        assert meta.has_sections is True
        assert meta.sources_count == 0

    def test_accepts_map_with_only_mappings(self) -> None:
        body = json.dumps({"version": 3, "mappings": "AAAA"})
        meta = parse_source_map(body)
        assert meta is not None
        assert meta.sources_count == 0
        assert meta.has_sections is False

    def test_records_source_root_flag(self) -> None:
        data = minimal_v3()
        data["sourceRoot"] = "/app/"
        meta = parse_source_map(json.dumps(data))
        assert meta is not None
        assert meta.has_source_root is True


class ShapeRejectionTests(unittest.TestCase):
    def test_empty_body_returns_none(self) -> None:
        assert parse_source_map("") is None

    def test_non_json_body_returns_none(self) -> None:
        # E.g. an HTML 404 page caught up to the body cap returns
        # text that doesn't parse as JSON. The validator must not
        # crash.
        assert parse_source_map("<html>not json</html>") is None

    def test_json_array_returns_none(self) -> None:
        # Top-level JSON arrays / scalars are valid JSON but the
        # Source Map v3 spec requires a top-level object.
        assert parse_source_map("[1, 2, 3]") is None

    def test_json_scalar_returns_none(self) -> None:
        assert parse_source_map('"just a string"') is None

    def test_missing_version_returns_none(self) -> None:
        body = json.dumps({"sources": ["x"], "mappings": "AAAA"})
        assert parse_source_map(body) is None

    def test_missing_all_payload_keys_returns_none(self) -> None:
        # Has version but none of sources/sections/mappings — not a
        # source map per spec.
        assert parse_source_map(json.dumps({"version": 3})) is None
