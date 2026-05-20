"""HTML-body capture + truncation tests for stub 1.3 fetcher."""
from __future__ import annotations

import unittest

from ..fetcher import FetcherConfig, fetch_evidence

from ._fetcher_helpers import _resp, mocked_fetcher


class HtmlBodyTests(unittest.TestCase):
    def test_returns_html_body_and_final_url(self) -> None:
        html = "<html><body>hello</body></html>"
        with mocked_fetcher({"https://x.example/": _resp(html)}):
            bundle = fetch_evidence("https://x.example/")

        assert bundle["html_body"] == html
        assert bundle["url"] == "https://x.example/"

    def test_truncates_html_body_to_max_body_bytes(self) -> None:
        huge = "x" * 5000
        config = FetcherConfig(max_body_bytes=1024)
        with mocked_fetcher({"https://x.example/": _resp(huge)}):
            bundle = fetch_evidence("https://x.example/", config=config)

        assert len(bundle["html_body"]) == 1024
