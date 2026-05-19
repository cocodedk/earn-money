"""Tests for the Source Map v3 validator + metadata extractor.

Stub 1.14 slice 4. Spec §"Source map fetch" requires the body to
parse as JSON with `version` plus at least one of `sources`,
`sections`, or `mappings`. Spec §"Extracted deterministic
attributes" pins the metadata shape the runner persists.
"""
from __future__ import annotations

import json
import unittest

from ..validator import SourceMapMetadata, parse_source_map


def _minimal_v3() -> dict:
    return {
        "version": 3,
        "file": "app.min.js",
        "sources": ["webpack://app/src/main.ts"],
        "sourcesContent": ["console.log('main');"],
        "names": [],
        "mappings": "AAAA",
    }


class ShapeAcceptanceTests(unittest.TestCase):
    def test_minimal_v3_parses(self) -> None:
        meta = parse_source_map(json.dumps(_minimal_v3()))
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
        data = _minimal_v3()
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

    def test_categorises_webpack_paths(self) -> None:
        body = json.dumps({
            "version": 3,
            "sources": [
                "webpack://app/src/main.ts",
                "webpack:///./node_modules/react/index.js",
            ],
            "mappings": "AAAA",
        })
        meta = parse_source_map(body)
        assert meta is not None
        assert "webpack" in meta.source_path_categories
        assert "node_modules" in meta.source_path_categories

    def test_categorises_framework_paths(self) -> None:
        body = json.dumps({
            "version": 3,
            "sources": [
                "/src/components/Login.tsx",  # react via .tsx ext
                "/pages/_app.vue",            # vue
                "/routes/+page.svelte",       # svelte
            ],
            "mappings": "AAAA",
        })
        meta = parse_source_map(body)
        assert meta is not None
        categories = set(meta.source_path_categories)
        assert {"react", "vue", "svelte"}.issubset(categories)

    def test_categorises_absolute_and_relative_paths(self) -> None:
        body = json.dumps({
            "version": 3,
            "sources": ["/home/builder/proj/x.ts", "./relative/y.ts"],
            "mappings": "AAAA",
        })
        meta = parse_source_map(body)
        assert meta is not None
        categories = set(meta.source_path_categories)
        assert "absolute_path" in categories
        assert "relative_path" in categories

    def test_categorises_url_source(self) -> None:
        body = json.dumps({
            "version": 3,
            "sources": ["https://cdn.example/lib.js"],
            "mappings": "AAAA",
        })
        meta = parse_source_map(body)
        assert meta is not None
        assert "url" in meta.source_path_categories

    def test_unknown_category_when_no_hint_matches(self) -> None:
        body = json.dumps({
            "version": 3,
            "sources": ["xyzzy"],  # no prefix, no path, no hint
            "mappings": "AAAA",
        })
        meta = parse_source_map(body)
        assert meta is not None
        assert "unknown" in meta.source_path_categories

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
        meta = parse_source_map(json.dumps(_minimal_v3()))
        assert isinstance(meta, SourceMapMetadata)

    def test_categorises_vite_paths(self) -> None:
        body = json.dumps({
            "version": 3,
            "sources": ["/some/path/.vite/cache.js", "vite:dev"],
            "mappings": "AAAA",
        })
        meta = parse_source_map(body)
        assert meta is not None
        assert "vite" in meta.source_path_categories

    def test_categorises_nextjs_paths(self) -> None:
        body = json.dumps({
            "version": 3,
            "sources": ["/.next/static/main.js", "/_next/dist/x.js"],
            "mappings": "AAAA",
        })
        meta = parse_source_map(body)
        assert meta is not None
        assert "nextjs" in meta.source_path_categories

    def test_categorises_angular_paths(self) -> None:
        body = json.dumps({
            "version": 3,
            "sources": ["/.angular/cache/main.js", "ng:internal/x"],
            "mappings": "AAAA",
        })
        meta = parse_source_map(body)
        assert meta is not None
        assert "angular" in meta.source_path_categories

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
