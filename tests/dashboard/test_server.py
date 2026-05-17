"""Tests for the dashboard HTTP server."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest

from earn_money.dashboard import server
from tests.triage.conftest import engine_paths


def _start(paths: object, port: int = 0) -> ThreadingHTTPServer:
    httpd = server.build(paths, port=port)  # type: ignore[arg-type]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


@pytest.fixture
def running_server(tmp_repo: Path) -> Iterator[tuple[ThreadingHTTPServer, str]]:
    paths = engine_paths(tmp_repo)
    httpd = _start(paths)
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        yield httpd, base
    finally:
        httpd.shutdown()


def test_status_endpoint_returns_json(
    running_server: tuple[ThreadingHTTPServer, str],
) -> None:
    _, base = running_server
    with httpx.Client() as c:
        r = c.get(f"{base}/api/status", timeout=2)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    body = r.json()
    assert "programs" in body
    assert "across" in body


def test_root_returns_html_with_title(
    running_server: tuple[ThreadingHTTPServer, str],
) -> None:
    _, base = running_server
    with httpx.Client() as c:
        r = c.get(f"{base}/", timeout=2)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "<title>earn-money dashboard</title>" in r.text


def test_static_tokens_css_is_served_with_css_content_type(
    running_server: tuple[ThreadingHTTPServer, str],
) -> None:
    _, base = running_server
    with httpx.Client() as c:
        r = c.get(f"{base}/static/tokens.css", timeout=2)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/css")
    # Sanity check that the actual tokens CSS — not the HTML — was sent.
    assert ":root" in r.text and "--paper" in r.text


def test_static_dashboard_css_is_served_with_css_content_type(
    running_server: tuple[ThreadingHTTPServer, str],
) -> None:
    _, base = running_server
    with httpx.Client() as c:
        r = c.get(f"{base}/static/dashboard.css", timeout=2)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/css")
    # Layout-level selector lives in dashboard.css, not tokens.css.
    assert "article.program" in r.text


def test_static_dashboard_js_is_served_with_js_content_type(
    running_server: tuple[ThreadingHTTPServer, str],
) -> None:
    _, base = running_server
    with httpx.Client() as c:
        r = c.get(f"{base}/static/dashboard.js", timeout=2)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/javascript")
    # Polling lives in dashboard.js.
    assert "/api/status" in r.text


def test_static_render_js_is_served_with_js_content_type(
    running_server: tuple[ThreadingHTTPServer, str],
) -> None:
    _, base = running_server
    with httpx.Client() as c:
        r = c.get(f"{base}/static/render.js", timeout=2)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/javascript")
    # Render functions live in render.js.
    assert "renderAcross" in r.text and "renderPrograms" in r.text


def test_static_render_panels_js_is_served(
    running_server: tuple[ThreadingHTTPServer, str],
) -> None:
    _, base = running_server
    with httpx.Client() as c:
        r = c.get(f"{base}/static/render_panels.js", timeout=2)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/javascript")
    assert "renderActiveRuns" in r.text
    assert "renderRecentSignals" in r.text


def test_static_panels_css_is_served(
    running_server: tuple[ThreadingHTTPServer, str],
) -> None:
    _, base = running_server
    with httpx.Client() as c:
        r = c.get(f"{base}/static/panels.css", timeout=2)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/css")
    assert ".sigtype" in r.text


def test_static_probe_status_js_is_served(
    running_server: tuple[ThreadingHTTPServer, str],
) -> None:
    _, base = running_server
    with httpx.Client() as c:
        r = c.get(f"{base}/static/probe-status.js", timeout=2)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/javascript")
    assert "getTurnStatus" in r.text and "formatTurnStatus" in r.text


def test_static_probe_state_js_is_served(
    running_server: tuple[ThreadingHTTPServer, str],
) -> None:
    _, base = running_server
    with httpx.Client() as c:
        r = c.get(f"{base}/static/probe-state.js", timeout=2)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/javascript")
    assert "probeReducer" in r.text and "probeState" in r.text


def test_static_probe_detail_css_is_served(
    running_server: tuple[ThreadingHTTPServer, str],
) -> None:
    _, base = running_server
    with httpx.Client() as c:
        r = c.get(f"{base}/static/probe-detail.css", timeout=2)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/css")
    assert ".probe-body" in r.text


def test_static_probe_detail_js_is_served(
    running_server: tuple[ThreadingHTTPServer, str],
) -> None:
    _, base = running_server
    with httpx.Client() as c:
        r = c.get(f"{base}/static/probe-detail.js", timeout=2)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/javascript")
    assert "renderDetailPanel" in r.text


def test_unknown_path_returns_404(
    running_server: tuple[ThreadingHTTPServer, str],
) -> None:
    _, base = running_server
    with httpx.Client() as c:
        r = c.get(f"{base}/no-such-route", timeout=2)
    assert r.status_code == 404


def test_static_route_ignores_query_string(
    running_server: tuple[ThreadingHTTPServer, str],
) -> None:
    """A cache-buster (`?v=2`) on a known static asset must still
    resolve, not 404 silently."""
    _, base = running_server
    with httpx.Client() as c:
        r = c.get(f"{base}/static/tokens.css?v=2", timeout=2)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/css")
