"""Tests for the Source Map v3 validator metadata extraction.

Stub 1.14 slice 4. Shape acceptance / rejection lives in
`test_validator_shape.py`; per-category classification lives in
`test_validator_categories.py`. This file covers everything else
the validator emits on a well-formed map: bounded sampling, input
filtering, internal-path indicators, counts, version handling, and
the dataclass return type.
"""
from __future__ import annotations

import json
import unittest

from ..validator import SourceMapMetadata, parse_source_map
from ._validator_factories import minimal_v3


class MetadataExtractionTests(unittest.TestCase):
    def test_source_path_samples_bounded_to_cap(self) -> None:
        # Use 20 sources but the runner only persists the first N
        # samples — keep the persisted record small. The cap is
        # exposed to allow the runner to read it back out for
        # configuration parity.
        sources = [f"webpack://app/src/file{i}.ts" for i in range(20)]
        body = json.dumps({
            "version": 3, "sources": sources, "mappings": "AAAA",
        })
        meta = parse_source_map(body)
        assert meta is not None
        assert len(meta.source_path_samples) <= 10
        assert all(s.startswith("webpack://") for s in meta.source_path_samples)

    def test_non_string_sources_filtered(self) -> None:
        # Spec doesn't require sources entries to be strings;
        # bundlers occasionally include `null`. Skip non-strings.
        body = json.dumps({
            "version": 3,
            "sources": ["webpack://app/x.ts", None, 42, "/src/y.js"],
            "mappings": "AAAA",
        })
        meta = parse_source_map(body)
        assert meta is not None
        assert meta.sources_count == 2
        assert meta.source_path_samples == (
            "webpack://app/x.ts", "/src/y.js",
        )

    def test_internal_path_indicators_detected(self) -> None:
        body = json.dumps({
            "version": 3,
            "sources": [
                "webpack://app/src/main.ts",
                "/home/user/build/x.ts",
                "C:\\Users\\dev\\project\\y.ts",
            ],
            "mappings": "AAAA",
        })
        meta = parse_source_map(body)
        assert meta is not None
        indicators = set(meta.internal_path_indicators)
        assert "/src/" in indicators
        assert "/home/" in indicators
        assert "C:\\" in indicators

    def test_empty_sources_yields_empty_metadata_collections(self) -> None:
        meta = parse_source_map(json.dumps({
            "version": 3, "sources": [], "mappings": "AAAA",
        }))
        assert meta is not None
        assert meta.source_path_samples == ()
        assert meta.source_path_categories == ()
        assert meta.internal_path_indicators == ()

    def test_sources_content_counted_independently_of_sources(self) -> None:
        # Some bundlers emit asymmetric counts (e.g. sourcesContent
        # has nulls for external sources). Pin both as separate ints.
        body = json.dumps({
            "version": 3,
            "sources": ["/a.ts", "/b.ts", "/c.ts"],
            "sourcesContent": ["a", None, "c"],
            "mappings": "AAAA",
        })
        meta = parse_source_map(body)
        assert meta is not None
        assert meta.sources_count == 3
        assert meta.sources_content_count == 3
        assert meta.has_sources_content is True

    def test_returns_dataclass_type(self) -> None:
        meta = parse_source_map(json.dumps(minimal_v3()))
        assert isinstance(meta, SourceMapMetadata)

    def test_version_string_returns_none_version(self) -> None:
        # Spec lists v3 as `3` (int); a stringified "3" is still
        # treated as a valid map shape if it has sources/mappings,
        # but the persisted `version` is None so the runner can see
        # the deviation in audit.
        body = json.dumps({
            "version": "3", "sources": ["/x.ts"], "mappings": "A",
        })
        meta = parse_source_map(body)
        assert meta is not None
        assert meta.version is None

    def test_version_boolean_returns_none_version(self) -> None:
        # In Python, bool is a subclass of int — a JSON `true` for
        # version would deserialize to True. Reject explicitly.
        body = json.dumps({
            "version": True, "sources": ["/x.ts"], "mappings": "A",
        })
        meta = parse_source_map(body)
        assert meta is not None
        assert meta.version is None
