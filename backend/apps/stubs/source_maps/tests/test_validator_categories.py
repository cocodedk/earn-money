"""Category-detection tests for the Source Map v3 validator.

Spec §"Extracted deterministic attributes": each source path is
classified into the closed vocabulary in `path_categories._CATEGORY_ORDER`
(12 values: webpack, vite, nextjs, angular, react, vue, svelte,
node_modules, absolute_path, relative_path, url, unknown). Multiple
categories can apply to one path.
"""
from __future__ import annotations

import json
import unittest

from ..validator import parse_source_map


class WebpackAndNodeModulesTests(unittest.TestCase):
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


class FrameworkExtensionTests(unittest.TestCase):
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


class PathShapeTests(unittest.TestCase):
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


class BuildToolTests(unittest.TestCase):
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
