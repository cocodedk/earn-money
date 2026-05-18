"""Fetcher tests for stub 1.3 frontend-framework.

The fetcher does:
1. GET base_url, capture body.
2. Parse for <script src>, <link rel=modulepreload>,
   <link rel=preload as=script>, <link rel=stylesheet>.
3. For each linked asset (same-origin by default, http/https only,
   within max_linked_assets count, within max_asset_bytes per body):
   GET the asset, capture its body keyed by filename.
4. Skip *.map files unless allow_source_map_fetch=True.
5. Cap html body to max_body_bytes.

httpx is mocked in every test — no real network.
"""
from __future__ import annotations

from unittest.mock import patch

import httpx
import unittest

from ..fetcher import FetcherConfig, fetch_evidence


def _resp(
    body: str,
    *,
    status_code: int = 200,
    url: str = "https://x.example/",
    content_type: str = "text/html",
) -> httpx.Response:
    req = httpx.Request("GET", url)
    return httpx.Response(
        status_code=status_code,
        headers={"Content-Type": content_type},
        content=body.encode("utf-8"),
        request=req,
    )


def _mock_client(responses: dict[str, httpx.Response]):
    """Return a side_effect that maps URL → mocked response.

    Unmocked URLs raise — tests must mock every URL they expect the
    fetcher to hit, so a request to an unmocked URL is a real test bug
    (forgot to mock something, or the fetcher is reaching somewhere it
    shouldn't)."""
    def side_effect(url, **_kwargs):
        if url in responses:
            return responses[url]
        raise AssertionError(f"unmocked URL: {url}")  # pragma: no cover  # defensive guard for test-bug detection
    return side_effect


class HtmlBodyTests(unittest.TestCase):
    def test_returns_html_body_and_final_url(self) -> None:
        html = "<html><body>hello</body></html>"
        responses = {"https://x.example/": _resp(html)}
        with patch("apps.stubs.server_headers.runner.fetch_evidence"):
            pass  # placeholder import-trigger
        with patch(
            "apps.stubs.frontend_framework.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = _mock_client(responses)
            bundle = fetch_evidence("https://x.example/")

        assert bundle["html_body"] == html
        assert bundle["url"] == "https://x.example/"

    def test_truncates_html_body_to_max_body_bytes(self) -> None:
        huge = "x" * 5000
        responses = {"https://x.example/": _resp(huge)}
        config = FetcherConfig(max_body_bytes=1024)
        with patch(
            "apps.stubs.frontend_framework.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = _mock_client(responses)
            bundle = fetch_evidence("https://x.example/", config=config)

        assert len(bundle["html_body"]) == 1024


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
        with patch(
            "apps.stubs.frontend_framework.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = _mock_client(responses)
            bundle = fetch_evidence("https://x.example/")

        assert "/static/main.js" in bundle["script_paths"]
        assert "/static/vendor.js" in bundle["script_paths"]


class AssetFetchTests(unittest.TestCase):
    def test_fetches_same_origin_scripts_and_returns_bodies(self) -> None:
        html = '''
            <html><head>
                <script src="/static/app.js"></script>
            </head></html>
        '''
        responses = {
            "https://x.example/": _resp(html),
            "https://x.example/static/app.js": _resp(
                "function react-dom(){}", content_type="application/javascript"
            ),
        }
        with patch(
            "apps.stubs.frontend_framework.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = _mock_client(responses)
            bundle = fetch_evidence("https://x.example/")

        assert "app.js" in bundle["asset_bodies"]
        assert "react-dom" in bundle["asset_bodies"]["app.js"]

    def test_skips_cross_origin_by_default(self) -> None:
        html = '<script src="https://cdn.other.example/lib.js"></script>'
        responses = {"https://x.example/": _resp(html)}
        with patch(
            "apps.stubs.frontend_framework.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = _mock_client(responses)
            bundle = fetch_evidence("https://x.example/")

        assert bundle["asset_bodies"] == {}

    def test_skips_non_http_schemes(self) -> None:
        # An absolute non-http(s) URL (e.g., ftp://) shouldn't be
        # fetched. Realistic? Unusual, but the safety net belongs.
        html = '<script src="ftp://x.example/lib.js"></script>'
        responses = {"https://x.example/": _resp(html)}
        with patch(
            "apps.stubs.frontend_framework.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = _mock_client(responses)
            bundle = fetch_evidence("https://x.example/")

        assert bundle["asset_bodies"] == {}

    def test_skips_source_maps_by_default(self) -> None:
        html = '<script src="/static/app.js.map"></script>'
        responses = {"https://x.example/": _resp(html)}
        with patch(
            "apps.stubs.frontend_framework.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = _mock_client(responses)
            bundle = fetch_evidence("https://x.example/")

        assert bundle["asset_bodies"] == {}

    def test_caps_at_max_linked_assets(self) -> None:
        html = "".join(
            f'<script src="/static/file{i}.js"></script>'
            for i in range(20)
        )
        responses = {"https://x.example/": _resp(html)}
        for i in range(20):
            responses[f"https://x.example/static/file{i}.js"] = _resp(
                f"// file {i}", content_type="application/javascript"
            )
        config = FetcherConfig(max_linked_assets=5)
        with patch(
            "apps.stubs.frontend_framework.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = _mock_client(responses)
            bundle = fetch_evidence("https://x.example/", config=config)

        # 5 assets fetched (cap); script_paths captures all 20.
        assert len(bundle["asset_bodies"]) == 5
        assert len(bundle["script_paths"]) == 20

    def test_skips_asset_over_max_asset_bytes(self) -> None:
        big_body = "y" * 5000
        html = '<script src="/static/big.js"></script>'
        responses = {
            "https://x.example/": _resp(html),
            "https://x.example/static/big.js": _resp(
                big_body, content_type="application/javascript"
            ),
        }
        config = FetcherConfig(max_asset_bytes=1024)
        with patch(
            "apps.stubs.frontend_framework.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = _mock_client(responses)
            bundle = fetch_evidence("https://x.example/", config=config)

        # Asset was over the cap — body truncated, but still recorded.
        assert "big.js" in bundle["asset_bodies"]
        assert len(bundle["asset_bodies"]["big.js"]) == 1024


class LinkTagExtractionTests(unittest.TestCase):
    def test_skips_link_without_href(self) -> None:
        # A bare <link rel="canonical"> with no href shouldn't crash or
        # add anything to script_paths.
        html = '<link rel="canonical">'
        responses = {"https://x.example/": _resp(html)}
        with patch(
            "apps.stubs.frontend_framework.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = _mock_client(responses)
            bundle = fetch_evidence("https://x.example/")

        assert bundle["script_paths"] == []

    def test_skips_non_asset_link_rels(self) -> None:
        # <link rel="icon">, <link rel="canonical">, etc. should not
        # be treated as assets.
        html = (
            '<link rel="icon" href="/favicon.ico">'
            '<link rel="canonical" href="https://x.example/">'
        )
        responses = {"https://x.example/": _resp(html)}
        with patch(
            "apps.stubs.frontend_framework.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = _mock_client(responses)
            bundle = fetch_evidence("https://x.example/")

        assert bundle["script_paths"] == []

    def test_extracts_preload_as_script(self) -> None:
        # rel="preload" with as="script" is a Vite/webpack pattern for
        # warming up bundles.
        html = (
            '<link rel="preload" as="script" '
            'href="/static/warm.js">'
        )
        responses = {
            "https://x.example/": _resp(html),
            "https://x.example/static/warm.js": _resp(
                "// warm", content_type="application/javascript"
            ),
        }
        with patch(
            "apps.stubs.frontend_framework.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = _mock_client(responses)
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
        with patch(
            "apps.stubs.frontend_framework.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = _mock_client(responses)
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
        with patch(
            "apps.stubs.frontend_framework.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = _mock_client(responses)
            bundle = fetch_evidence("https://x.example/")

        assert "/static/site.css" in bundle["script_paths"]
        assert "site.css" in bundle["asset_bodies"]


class TransportErrorTests(unittest.TestCase):
    def test_base_url_failure_returns_empty_bundle(self) -> None:
        with patch(
            "apps.stubs.frontend_framework.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = httpx.ConnectError("refused")
            bundle = fetch_evidence("https://x.example/")

        assert bundle["html_body"] == ""
        assert bundle["script_paths"] == []
        assert bundle["asset_bodies"] == {}

    def test_asset_failure_is_skipped_not_fatal(self) -> None:
        html = (
            '<script src="/static/ok.js"></script>'
            '<script src="/static/broken.js"></script>'
        )
        good = _resp("// ok", content_type="application/javascript")

        def side_effect(url, **_kwargs):
            if url == "https://x.example/":
                return _resp(html)
            if url == "https://x.example/static/ok.js":
                return good
            raise httpx.ConnectError(f"refused: {url}")

        with patch(
            "apps.stubs.frontend_framework.fetcher.httpx.Client"
        ) as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.get.side_effect = side_effect
            bundle = fetch_evidence("https://x.example/")

        # broken.js skipped; ok.js recorded.
        assert "ok.js" in bundle["asset_bodies"]
        assert "broken.js" not in bundle["asset_bodies"]
