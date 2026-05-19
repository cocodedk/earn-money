"""Tests for stub 1.12 fetch_sitemap — single GET with body cap."""
from __future__ import annotations

import unittest

import httpx

from ..fetcher import FetcherConfig, fetch_sitemap
from ._helpers import mocked_fetcher, resp


class OkTests(unittest.TestCase):
    def test_200_returns_ok_with_body(self) -> None:
        url = "https://x.example/sitemap.xml"
        with mocked_fetcher({
            "/sitemap.xml": resp(
                "<urlset></urlset>", status_code=200, url=url,
            ),
        }):
            outcome = fetch_sitemap(url)
        assert outcome.kind == "ok"
        assert outcome.status == 200
        assert outcome.body == "<urlset></urlset>"
        assert outcome.final_url.endswith("/sitemap.xml")

    def test_404_returns_ok_with_status(self) -> None:
        # 404 isn't "unreachable" — the server replied. Classify
        # decides what to do; the fetcher just surfaces the status.
        with mocked_fetcher({
            "/sitemap.xml": resp("not found", status_code=404),
        }):
            outcome = fetch_sitemap("https://x.example/sitemap.xml")
        assert outcome.kind == "ok"
        assert outcome.status == 404


class TruncationTests(unittest.TestCase):
    def test_body_within_cap_kept(self) -> None:
        body = "<urlset>" + "x" * 100 + "</urlset>"
        with mocked_fetcher({
            "/sitemap.xml": resp(body, status_code=200),
        }):
            outcome = fetch_sitemap(
                "https://x.example/sitemap.xml",
                config=FetcherConfig(max_body_bytes=10000),
            )
        assert outcome.kind == "ok"
        assert outcome.body == body

    def test_body_exceeds_cap_yields_too_large(self) -> None:
        big = "x" * 5000
        with mocked_fetcher({
            "/sitemap.xml": resp(big, status_code=200),
        }):
            outcome = fetch_sitemap(
                "https://x.example/sitemap.xml",
                config=FetcherConfig(max_body_bytes=1000),
            )
        assert outcome.kind == "too_large"
        # Body still surfaces the bounded sample so evidence can
        # record what was seen.
        assert outcome.body == big[:1000]


class TransportErrorTests(unittest.TestCase):
    def test_connect_error_returns_unreachable(self) -> None:
        def raise_(_url, **_kwargs):
            raise httpx.ConnectError("DNS timeout")
        with mocked_fetcher(get_side_effect=raise_):
            outcome = fetch_sitemap("https://x.example/sitemap.xml")
        assert outcome.kind == "unreachable"
        assert outcome.status is None

    def test_timeout_returns_unreachable(self) -> None:
        def raise_(_url, **_kwargs):
            raise httpx.ReadTimeout("slow server")
        with mocked_fetcher(get_side_effect=raise_):
            outcome = fetch_sitemap("https://x.example/sitemap.xml")
        assert outcome.kind == "unreachable"


class ConfigValidationTests(unittest.TestCase):
    def test_negative_max_body_bytes_rejected(self) -> None:
        with self.assertRaises(ValueError):
            FetcherConfig(max_body_bytes=-1)
