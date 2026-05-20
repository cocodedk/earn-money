"""Script + link extraction tests for stub 1.3 fetcher."""
from __future__ import annotations

import unittest

from ..fetcher import fetch_evidence

from ._fetcher_helpers import _resp, mocked_fetcher


class ScriptPathExtractionTests(unittest.TestCase):
    def test_extracts_script_src_paths(self) -> None:
        html = '''
            <html><head>
                <script src="/static/main.js"></script>
                <script src="https://x.example/static/vendor.js"></script>
            </head></html>
        '''
        responses = {
            "https://x.example/": _resp(html),
            "https://x.example/static/main.js": _resp(
                "console.log('main')", content_type="application/javascript"
            ),
            "https://x.example/static/vendor.js": _resp(
                "console.log('vendor')", content_type="application/javascript"
            ),
        }
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/")

        assert "/static/main.js" in bundle["script_paths"]
        assert "/static/vendor.js" in bundle["script_paths"]


class LinkTagExtractionTests(unittest.TestCase):
    def test_skips_link_without_href(self) -> None:
        html = '<link rel="canonical">'
        with mocked_fetcher({"https://x.example/": _resp(html)}):
            bundle = fetch_evidence("https://x.example/")
        assert bundle["script_paths"] == []

    def test_skips_non_asset_link_rels(self) -> None:
        html = (
            '<link rel="icon" href="/favicon.ico">'
            '<link rel="canonical" href="https://x.example/">'
        )
        with mocked_fetcher({"https://x.example/": _resp(html)}):
            bundle = fetch_evidence("https://x.example/")
        assert bundle["script_paths"] == []

    def test_extracts_preload_as_script(self) -> None:
        html = (
            '<link rel="preload" as="script" href="/static/warm.js">'
        )
        responses = {
            "https://x.example/": _resp(html),
            "https://x.example/static/warm.js": _resp(
                "// warm", content_type="application/javascript"
            ),
        }
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/")
        assert "/static/warm.js" in bundle["script_paths"]
        assert "warm.js" in bundle["asset_bodies"]

    def test_extracts_modulepreload_link(self) -> None:
        html = (
            '<link rel="modulepreload" href="/static/chunk.js">'
            '<script src="/static/main.js"></script>'
        )
        responses = {
            "https://x.example/": _resp(html),
            "https://x.example/static/chunk.js": _resp(
                "// chunk", content_type="application/javascript"
            ),
            "https://x.example/static/main.js": _resp(
                "// main", content_type="application/javascript"
            ),
        }
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/")
        assert "/static/chunk.js" in bundle["script_paths"]
        assert "chunk.js" in bundle["asset_bodies"]

    def test_extracts_stylesheet_link(self) -> None:
        html = '<link rel="stylesheet" href="/static/site.css">'
        responses = {
            "https://x.example/": _resp(html),
            "https://x.example/static/site.css": _resp(
                "body{}", content_type="text/css"
            ),
        }
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/")
        assert "/static/site.css" in bundle["script_paths"]
        assert "site.css" in bundle["asset_bodies"]
