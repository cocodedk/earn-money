"""End-to-end wiring test for the dashboard.

Spins up the real server on an ephemeral port against a seeded repo,
fetches both endpoints, and asserts that aggregator + server + HTML
template are wired together. Per-layer behaviour (aggregator shapes,
server route edge cases, template internals) is covered by their own
unit tests — this file exists only to catch wiring bugs.
"""

from __future__ import annotations

import threading
from pathlib import Path

import httpx

from earn_money.dashboard import server
from tests.triage.conftest import engine_paths


def test_e2e_wiring(tmp_repo: Path) -> None:
    """Aggregator + server + HTML template all connect through real HTTP."""
    paths = engine_paths(tmp_repo)
    httpd = server.build(paths, port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}") as c:
            api = c.get("/api/status", timeout=2)
            html = c.get("/", timeout=2)
    finally:
        httpd.shutdown()

    assert api.status_code == 200
    assert api.headers["content-type"].startswith("application/json")
    body = api.json()
    assert "programs" in body and "across" in body
    assert "generated_at" in body

    assert html.status_code == 200
    assert html.headers["content-type"].startswith("text/html")
    assert "<title>earn-money dashboard</title>" in html.text
