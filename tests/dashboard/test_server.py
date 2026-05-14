"""Tests for the dashboard HTTP server."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
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


def test_unknown_path_returns_404(
    running_server: tuple[ThreadingHTTPServer, str],
) -> None:
    _, base = running_server
    with httpx.Client() as c:
        r = c.get(f"{base}/no-such-route", timeout=2)
    assert r.status_code == 404


def test_concurrent_status_requests_both_complete(
    running_server: tuple[ThreadingHTTPServer, str],
) -> None:
    _, base = running_server

    def _fetch() -> int:
        with httpx.Client() as c:
            return c.get(f"{base}/api/status", timeout=5).status_code

    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = [ex.submit(_fetch), ex.submit(_fetch)]
        results = [f.result(timeout=10) for f in futures]
    assert results == [200, 200]


def test_bind_host_is_loopback(tmp_repo: Path) -> None:
    paths = engine_paths(tmp_repo)
    httpd = server.build(paths, port=0)
    try:
        assert httpd.server_address[0] == "127.0.0.1"
    finally:
        httpd.server_close()
