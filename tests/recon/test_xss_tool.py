"""Tests for xss_tool — reflected-XSS marker injection."""

from __future__ import annotations

import httpx

from earn_money.recon import xss_tool


def _client_returning(body: str) -> httpx.Client:
    def _handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)
    return httpx.Client(transport=httpx.MockTransport(_handler))


def test_probe_url_empty_for_no_params() -> None:
    with _client_returning("page content") as client:
        sigs = xss_tool.probe_url(
            "https://target.cocode.dk/page",
            client=client, run_id="r1", observed_at="t",
        )
    assert sigs == []


def test_probe_url_detects_reflection() -> None:
    reflected_body: list[str] = []

    def _handler(req: httpx.Request) -> httpx.Response:
        query = req.url.query.decode() if isinstance(req.url.query, bytes) else req.url.query
        q = dict(p.split("=") for p in query.split("&") if "=" in p)
        body = q.get("q", "not found")
        reflected_body.append(body)
        return httpx.Response(200, text=body)

    transport = httpx.MockTransport(_handler)
    with httpx.Client(transport=transport) as client:
        sigs = xss_tool.probe_url(
            "https://target.cocode.dk/search?q=test",
            client=client, run_id="r1", observed_at="t",
        )
    assert len(sigs) == 1
    assert sigs[0].signal_type == "xss_candidate"
    assert "reflected" in sigs[0].signature


def test_probe_url_no_signal_when_not_reflected() -> None:
    with _client_returning("static page") as client:
        sigs = xss_tool.probe_url(
            "https://target.cocode.dk/search?q=test",
            client=client, run_id="r1", observed_at="t",
        )
    assert sigs == []


def test_probe_url_swallows_http_error() -> None:
    def _fail(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    with httpx.Client(transport=httpx.MockTransport(_fail)) as client:
        sigs = xss_tool.probe_url(
            "https://target.cocode.dk/s?q=x",
            client=client, run_id="r1", observed_at="t",
        )
    assert sigs == []
