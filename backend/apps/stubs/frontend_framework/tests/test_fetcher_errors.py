"""Transport-error + config-validation tests for stub 1.3 fetcher."""
from __future__ import annotations

import unittest

import httpx
import pytest

from ..fetcher import FetcherConfig, fetch_evidence

from ._fetcher_helpers import _resp, mocked_fetcher


class TransportErrorTests(unittest.TestCase):
    def test_base_url_failure_returns_empty_bundle(self) -> None:
        with mocked_fetcher(get_side_effect=httpx.ConnectError("refused")):
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

        with mocked_fetcher(get_side_effect=side_effect):
            bundle = fetch_evidence("https://x.example/")

        assert "ok.js" in bundle["asset_bodies"]
        assert "broken.js" not in bundle["asset_bodies"]


class FetcherConfigValidationTests(unittest.TestCase):
    def test_negative_max_linked_assets_raises(self) -> None:
        with pytest.raises(ValueError, match="max_linked_assets"):
            FetcherConfig(max_linked_assets=-1)

    def test_negative_max_asset_bytes_raises(self) -> None:
        with pytest.raises(ValueError, match="max_asset_bytes"):
            FetcherConfig(max_asset_bytes=-1)

    def test_negative_max_body_bytes_raises(self) -> None:
        with pytest.raises(ValueError, match="max_body_bytes"):
            FetcherConfig(max_body_bytes=-1)
