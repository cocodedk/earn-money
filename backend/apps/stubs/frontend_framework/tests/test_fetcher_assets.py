"""Asset-fetch policy tests for stub 1.3 fetcher."""
from __future__ import annotations

import unittest

from ..fetcher import FetcherConfig, fetch_evidence

from ._fetcher_helpers import _resp, mocked_fetcher


class AssetFetchTests(unittest.TestCase):
    def test_fetches_same_origin_scripts_and_returns_bodies(self) -> None:
        html = '<script src="/static/app.js"></script>'
        responses = {
            "https://x.example/": _resp(html),
            "https://x.example/static/app.js": _resp(
                "function react-dom(){}",
                content_type="application/javascript",
            ),
        }
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/")
        assert "app.js" in bundle["asset_bodies"]
        assert "react-dom" in bundle["asset_bodies"]["app.js"]

    def test_skips_cross_origin_by_default(self) -> None:
        html = '<script src="https://cdn.other.example/lib.js"></script>'
        with mocked_fetcher({"https://x.example/": _resp(html)}):
            bundle = fetch_evidence("https://x.example/")
        assert bundle["asset_bodies"] == {}

    def test_skips_non_http_schemes(self) -> None:
        # An absolute non-http(s) URL (e.g., ftp://) shouldn't be fetched.
        html = '<script src="ftp://x.example/lib.js"></script>'
        with mocked_fetcher({"https://x.example/": _resp(html)}):
            bundle = fetch_evidence("https://x.example/")
        assert bundle["asset_bodies"] == {}

    def test_skips_source_maps_by_default(self) -> None:
        html = '<script src="/static/app.js.map"></script>'
        with mocked_fetcher({"https://x.example/": _resp(html)}):
            bundle = fetch_evidence("https://x.example/")
        assert bundle["asset_bodies"] == {}

    def test_caps_at_max_linked_assets(self) -> None:
        html = "".join(
            f'<script src="/static/file{i}.js"></script>' for i in range(20)
        )
        responses = {"https://x.example/": _resp(html)}
        for i in range(20):
            responses[f"https://x.example/static/file{i}.js"] = _resp(
                f"// file {i}", content_type="application/javascript"
            )
        config = FetcherConfig(max_linked_assets=5)
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/", config=config)

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
        with mocked_fetcher(responses):
            bundle = fetch_evidence("https://x.example/", config=config)

        assert "big.js" in bundle["asset_bodies"]
        assert len(bundle["asset_bodies"]["big.js"]) == 1024


class ProtocolRelativeTests(unittest.TestCase):
    def test_protocol_relative_resolved_as_cross_origin(self) -> None:
        # `//cdn.other.example/lib.js` resolves to https://cdn.other.example/
        # under the base URL's scheme; same-origin filter must classify
        # it as cross-origin and skip the fetch (unless allow_external).
        html = '<script src="//cdn.other.example/lib.js"></script>'
        with mocked_fetcher({"https://x.example/": _resp(html)}):
            bundle = fetch_evidence("https://x.example/")
        assert bundle["asset_bodies"] == {}
