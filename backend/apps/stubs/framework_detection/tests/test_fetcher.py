"""HTTP fetcher tests — mock httpx; no real network."""
from __future__ import annotations

import unittest
from http.cookiejar import Cookie
from unittest.mock import MagicMock, patch

from ..fetcher import _basename, fetch_evidence


def _make_mock_response(*, text="", headers=None, cookies=None, url="https://x"):
    """Build a MagicMock that quacks like httpx.Response enough for the fetcher."""
    response = MagicMock()
    response.text = text
    response.headers = headers or {}
    response.url = url
    response.status_code = 200
    jar = MagicMock()
    jar.__iter__ = lambda _self: iter(cookies or [])
    cookies_obj = MagicMock()
    cookies_obj.jar = jar
    response.cookies = cookies_obj
    return response


def _cookie(name: str, value: str) -> Cookie:
    return Cookie(
        version=0, name=name, value=value, port=None, port_specified=False,
        domain="x", domain_specified=True, domain_initial_dot=False,
        path="/", path_specified=True, secure=False, expires=None,
        discard=True, comment=None, comment_url=None, rest={},
    )


class BasenameTests(unittest.TestCase):
    def test_strips_directory(self) -> None:
        assert _basename("/static/main.123.js") == "main.123.js"

    def test_handles_absolute_url(self) -> None:
        assert _basename("https://cdn.example/a/b/c.js") == "c.js"

    def test_handles_bare_name(self) -> None:
        assert _basename("main.js") == "main.js"


class FetchEvidenceTests(unittest.TestCase):
    @patch("apps.stubs.framework_detection.fetcher.httpx.Client")
    def test_collects_headers_cookies_body_scripts(self, mock_client_class) -> None:
        mock_response = _make_mock_response(
            text=(
                "<html><body>"
                "<script src='/static/runtime.123.js'></script>"
                "<script src='https://cdn.example/main.abc.js'></script>"
                "</body></html>"
            ),
            headers={"X-Powered-By": "PHP/8.2", "Server": "Apache"},
            cookies=[_cookie("PHPSESSID", "abc")],
            url="https://target.example",
        )
        client = MagicMock()
        client.get.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = client

        bundle = fetch_evidence("https://target.example")

        assert bundle["headers"]["X-Powered-By"] == "PHP/8.2"
        assert {"name": "PHPSESSID", "value": "abc"} in bundle["cookies"]
        assert "<script" in bundle["html_body"]
        assert "runtime.123.js" in bundle["script_names"]
        assert "main.abc.js" in bundle["script_names"]
        assert bundle["status_code"] == 200
