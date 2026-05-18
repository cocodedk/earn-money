"""Fetcher contract for stub 1.2 server-headers.

The fetcher sends HEAD / first (cheapest, no body). If the server
rejects HEAD (405, 501) or returns an empty header set, fall back to
GET /. Redirects are followed within max_redirects; each hop's headers
are captured for redirect-chain evidence.

httpx is mocked in every test — no real network.
"""
from __future__ import annotations

from unittest.mock import patch

import httpx
import unittest

from ..fetcher import fetch_evidence


def _resp(
    status_code: int = 200,
    headers: dict[str, str] | None = None,
    method: str = "GET",
    url: str = "https://x.example/",
) -> httpx.Response:
    req = httpx.Request(method, url)
    return httpx.Response(
        status_code=status_code,
        headers=headers or {},
        request=req,
    )


class HappyHeadTests(unittest.TestCase):
    def test_head_returns_headers_no_get_needed(self) -> None:
        head = _resp(200, {"Server": "nginx/1.24.0"}, "HEAD")
        with patch("apps.stubs.server_headers.fetcher.httpx.Client") as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.head.return_value = head
            instance.get.side_effect = AssertionError("GET should not run")

            ev = fetch_evidence("https://x.example/")

        assert ev["method"] == "HEAD"
        assert ev["status_code"] == 200
        assert ev["headers"]["server"] == "nginx/1.24.0"
        assert ev["url"] == "https://x.example/"


class HeadFallbackToGetTests(unittest.TestCase):
    def test_405_falls_back_to_get(self) -> None:
        head = _resp(405, {"Allow": "GET, POST"}, "HEAD")
        get = _resp(200, {"Server": "Apache/2.4.58"}, "GET")
        with patch("apps.stubs.server_headers.fetcher.httpx.Client") as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.head.return_value = head
            instance.get.return_value = get

            ev = fetch_evidence("https://x.example/")

        assert ev["method"] == "GET"
        assert ev["status_code"] == 200
        assert ev["headers"]["server"] == "Apache/2.4.58"

    def test_501_falls_back_to_get(self) -> None:
        head = _resp(501, {}, "HEAD")
        get = _resp(200, {"Server": "nginx"}, "GET")
        with patch("apps.stubs.server_headers.fetcher.httpx.Client") as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.head.return_value = head
            instance.get.return_value = get
            ev = fetch_evidence("https://x.example/")
        assert ev["method"] == "GET"

    def test_empty_head_headers_falls_back_to_get(self) -> None:
        head = _resp(200, {}, "HEAD")
        get = _resp(200, {"Server": "Caddy"}, "GET")
        with patch("apps.stubs.server_headers.fetcher.httpx.Client") as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.head.return_value = head
            instance.get.return_value = get

            ev = fetch_evidence("https://x.example/")

        assert ev["method"] == "GET"
        assert ev["headers"]["server"] == "Caddy"


class TlsFailureTests(unittest.TestCase):
    def test_head_connect_error_falls_back_to_get(self) -> None:
        """A TransportError on HEAD shouldn't abort the fetch — try GET."""
        get = _resp(200, {"Server": "nginx"}, "GET")
        with patch("apps.stubs.server_headers.fetcher.httpx.Client") as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.head.side_effect = httpx.ConnectError("connection refused")
            instance.get.return_value = get

            ev = fetch_evidence("https://x.example/")

        assert ev["method"] == "GET"
        assert ev["status_code"] == 200


class RedirectChainTests(unittest.TestCase):
    def test_history_headers_captured(self) -> None:
        """When httpx follows redirects, the .history attribute carries
        each hop. The fetcher records every hop's status + Location."""
        req = httpx.Request("GET", "https://x.example/")
        hop1 = httpx.Response(
            301, headers={"Location": "https://x.example/new"}, request=req
        )
        final = _resp(200, {"Server": "nginx"}, "GET", "https://x.example/new")
        final.history = (hop1,)

        with patch("apps.stubs.server_headers.fetcher.httpx.Client") as mock_client:
            instance = mock_client.return_value.__enter__.return_value
            instance.head.return_value = final
            ev = fetch_evidence("https://x.example/")

        assert ev["url"] == "https://x.example/new"
        chain = ev["redirect_chain"]
        assert len(chain) == 1
        assert chain[0]["status_code"] == 301
        assert chain[0]["headers"]["location"] == "https://x.example/new"
