from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
from apps.agent.browser.driver import PlaywrightDriver, ScopeViolationError, MAX_ASSET_SIZE


def _driver() -> PlaywrightDriver:
    d = PlaywrightDriver()
    d._base_url = "https://example.com"
    d._base_host = "example.com"
    mock_page = MagicMock()
    mock_page.on = MagicMock()
    d._page = mock_page
    return d


def run(coro):
    return asyncio.run(coro)


class TestIsInScope:
    def test_same_host_https(self):
        assert _driver().is_in_scope("https://example.com/path") is True

    def test_same_host_http(self):
        assert _driver().is_in_scope("http://example.com/path") is True

    def test_different_host(self):
        assert _driver().is_in_scope("https://evil.com/path") is False

    def test_protocol_relative(self):
        assert _driver().is_in_scope("//example.com/path") is False

    def test_javascript_scheme(self):
        assert _driver().is_in_scope("javascript:alert(1)") is False

    def test_data_scheme(self):
        assert _driver().is_in_scope("data:text/html,<h1>x</h1>") is False

    def test_file_scheme(self):
        assert _driver().is_in_scope("file:///etc/passwd") is False

    def test_ftp_scheme(self):
        assert _driver().is_in_scope("ftp://example.com/") is False


class TestNavigate:
    def test_navigate_in_scope(self):
        d = _driver()
        d._page.goto = AsyncMock()
        run(d.navigate("/login"))
        d._page.goto.assert_called_once_with("https://example.com/login")

    def test_navigate_out_of_scope_raises(self):
        d = _driver()
        try:
            run(d.navigate("https://evil.com/"))
            assert False, "Expected ScopeViolationError"
        except ScopeViolationError:
            pass

    def test_navigate_absolute_in_scope(self):
        d = _driver()
        d._page.goto = AsyncMock()
        run(d.navigate("https://example.com/admin"))
        d._page.goto.assert_called_once_with("https://example.com/admin")


class TestFetchAsset:
    def test_fetch_small_asset(self):
        d = _driver()
        mock_response = AsyncMock()
        mock_response.body = AsyncMock(return_value=b"console.log('hi')")
        d._page.request = MagicMock()
        d._page.request.get = AsyncMock(return_value=mock_response)

        result = run(d.fetch_asset("/static/app.js"))
        assert result["content"] == "console.log('hi')"
        assert result["size_bytes"] == 17
        assert result["truncated"] is False

    def test_fetch_large_asset_truncates(self):
        d = _driver()
        large_content = b"x" * (MAX_ASSET_SIZE + 500)
        mock_response = AsyncMock()
        mock_response.body = AsyncMock(return_value=large_content)
        d._page.request = MagicMock()
        d._page.request.get = AsyncMock(return_value=mock_response)

        result = run(d.fetch_asset("/big.js"))
        assert result["truncated"] is True
        assert result["size_bytes"] == MAX_ASSET_SIZE + 500
        assert len(result["content"]) == MAX_ASSET_SIZE

    def test_fetch_out_of_scope_raises(self):
        d = _driver()
        try:
            run(d.fetch_asset("https://evil.com/malware.js"))
            assert False, "Expected ScopeViolationError"
        except ScopeViolationError:
            pass


class TestNetworkLog:
    def test_drain_returns_entries(self):
        d = _driver()
        d._network_log = [
            {"url": "https://example.com/api", "status": 200, "method": "GET"}
        ]
        log = d.drain_network_log()
        assert len(log) == 1
        assert log[0]["status"] == 200

    def test_drain_clears_log(self):
        d = _driver()
        d._network_log = [{"url": "x", "status": 200, "method": "GET"}]
        d.drain_network_log()
        assert d._network_log == []

    def test_on_response_appends(self):
        d = _driver()
        mock_response = MagicMock()
        mock_response.url = "https://example.com/api"
        mock_response.status = 201
        mock_response.request.method = "POST"
        d._on_response(mock_response)
        assert len(d._network_log) == 1
        entry = d._network_log[0]
        assert entry["status"] == 201
        assert entry["method"] == "POST"


class TestMaxAssetSize:
    def test_constant_value(self):
        assert MAX_ASSET_SIZE == 100_000
