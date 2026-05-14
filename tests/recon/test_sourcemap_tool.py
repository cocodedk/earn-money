"""Tests for sourcemap_tool — URL extraction, sourcemap-comment parsing,
end-to-end scan_target with a mocked HTTP transport."""

from __future__ import annotations

import httpx

from earn_money.recon import sourcemap_tool


def _accept_example_com(host: str) -> bool:
    return host.endswith("example.com")


def _accept_all(_host: str) -> bool:
    return True


def test_extract_script_urls_resolves_relative() -> None:
    html = (
        '<script src="/static/app.js"></script>\n'
        '<script src="https://cdn.example.com/vendor.js"></script>\n'
        '<script>inline</script>\n'
    )
    urls = sourcemap_tool.extract_script_urls(html, "https://app.example.com/")
    assert urls == [
        "https://app.example.com/static/app.js",
        "https://cdn.example.com/vendor.js",
    ]


def test_find_sourcemap_url_present() -> None:
    js = "var x = 1;\n//# sourceMappingURL=app.js.map\n"
    assert sourcemap_tool.find_sourcemap_url(
        js, "https://example.com/static/app.js",
    ) == "https://example.com/static/app.js.map"


def test_find_sourcemap_url_absent() -> None:
    assert sourcemap_tool.find_sourcemap_url("var x = 1;", "https://x/") is None


def _mock_client(routes: dict[str, tuple[int, str]]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url in routes:
            status, body = routes[url]
            return httpx.Response(status, text=body)
        return httpx.Response(404, text="not found")
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_scan_target_finds_secret_in_bundle() -> None:
    routes = {
        "https://app.example.com/":
            (200, '<script src="/app.js"></script>'),
        "https://app.example.com/app.js":
            (200, 'const k = "AKIAIOSFODNN7EXAMPLE";'),
    }
    with _mock_client(routes) as client:
        result = sourcemap_tool.scan_target(
            "https://app.example.com/",
            client=client,
            in_scope=_accept_example_com,
            run_id="r1",
            observed_at="t",
        )
    assert result.scripts_fetched == 1
    assert result.sourcemaps_fetched == 0
    assert len(result.signals) == 1
    sig = result.signals[0]
    assert sig.signal_type == "leaked_secret"
    assert sig.tool == "sourcemap-scan"
    assert sig.asset == "app.example.com"
    assert "AKIA" in sig.signature


def test_scan_target_fetches_sourcemap_when_present() -> None:
    routes = {
        "https://app.example.com/":
            (200, '<script src="/app.js"></script>'),
        "https://app.example.com/app.js":
            (200, "console.log(1);\n//# sourceMappingURL=app.js.map\n"),
        "https://app.example.com/app.js.map":
            (200, '{"version":3,"sources":["a.js"]}'),
    }
    with _mock_client(routes) as client:
        result = sourcemap_tool.scan_target(
            "https://app.example.com/",
            client=client,
            in_scope=_accept_example_com,
            run_id="r1",
            observed_at="t",
        )
    assert result.sourcemaps_fetched == 1
    types = {s.signal_type for s in result.signals}
    assert "exposed_sourcemap" in types


def test_scan_target_skips_out_of_scope_scripts() -> None:
    routes = {
        "https://app.example.com/":
            (200, '<script src="https://attacker.com/evil.js"></script>'),
        # If we fetched the OOS script the mock would record it, but the
        # scope filter must drop it before any GET goes out.
        "https://attacker.com/evil.js":
            (200, 'const k = "AKIAIOSFODNN7EXAMPLE";'),
    }
    with _mock_client(routes) as client:
        result = sourcemap_tool.scan_target(
            "https://app.example.com/",
            client=client,
            in_scope=_accept_example_com,
            run_id="r1",
            observed_at="t",
        )
    assert result.scripts_fetched == 0
    assert result.signals == ()


def test_scan_target_handles_404_html_silently() -> None:
    with _mock_client({}) as client:
        result = sourcemap_tool.scan_target(
            "https://app.example.com/",
            client=client,
            in_scope=_accept_all,
            run_id="r1",
            observed_at="t",
        )
    assert result == sourcemap_tool.ScanResult(
        signals=(), scripts_fetched=0, sourcemaps_fetched=0,
    )


def test_scan_target_handles_network_error_silently() -> None:
    def boom(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated")
    with httpx.Client(transport=httpx.MockTransport(boom)) as client:
        result = sourcemap_tool.scan_target(
            "https://app.example.com/",
            client=client,
            in_scope=_accept_all,
            run_id="r1",
            observed_at="t",
        )
    assert result.signals == ()
