"""Tests for sqli_tool — error-based and boolean-based probe logic."""

from __future__ import annotations

import httpx

from earn_money.recon import sqli_tool


def _make_client(responses: dict[str, str]) -> httpx.Client:
    """Returns an httpx.Client backed by a simple URL→body map."""
    def _handler(request: httpx.Request) -> httpx.Response:
        body = responses.get(str(request.url), "")
        return httpx.Response(200, text=body)

    transport = httpx.MockTransport(_handler)
    return httpx.Client(transport=transport)


def test_probe_url_returns_empty_for_url_without_params() -> None:
    client = _make_client({})
    sigs = sqli_tool.probe_url(
        "https://target.cocode.dk/page",
        client=client, run_id="r1", observed_at="t",
    )
    assert sigs == []


def test_probe_url_detects_error_based_sqli() -> None:
    url = "https://target.cocode.dk/search?q=test"
    err_url = "https://target.cocode.dk/search?q=%27"  # ' URL-encoded
    responses = {err_url: "you have an error in your sql syntax near 'test'"}
    with _make_client(responses) as client:
        sigs = sqli_tool.probe_url(url, client=client, run_id="r1", observed_at="t")
    assert len(sigs) == 1
    assert sigs[0].signal_type == "sqli_candidate"
    assert "error_based" in sigs[0].signature


def test_probe_url_detects_boolean_based_sqli() -> None:
    url = "https://target.cocode.dk/item?id=1"
    responses: dict[str, str] = {}
    # Normal response — short
    responses["https://target.cocode.dk/item?id=%27"] = "x" * 50
    # Boolean true — long (indicates data returned)
    responses["https://target.cocode.dk/item?id=%27+OR+%271%27%3D%271"] = "x" * 500
    # Boolean false — short (no data)
    responses["https://target.cocode.dk/item?id=%27+OR+%271%27%3D%272"] = "x" * 50
    with _make_client(responses) as client:
        sigs = sqli_tool.probe_url(url, client=client, run_id="r1", observed_at="t")
    assert len(sigs) == 1
    assert "boolean_based" in sigs[0].signature


def test_probe_url_no_signal_when_responses_identical() -> None:
    url = "https://target.cocode.dk/page?x=1"
    body = "same content every time"
    responses: dict[str, str] = {
        "https://target.cocode.dk/page?x=%27": body,
        "https://target.cocode.dk/page?x=%27+OR+%271%27%3D%271": body,
        "https://target.cocode.dk/page?x=%27+OR+%271%27%3D%272": body,
    }
    with _make_client(responses) as client:
        sigs = sqli_tool.probe_url(url, client=client, run_id="r1", observed_at="t")
    assert sigs == []


def test_probe_url_swallows_http_errors() -> None:
    def _fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    transport = httpx.MockTransport(_fail)
    with httpx.Client(transport=transport) as client:
        sigs = sqli_tool.probe_url(
            "https://target.cocode.dk/search?q=x",
            client=client, run_id="r1", observed_at="t",
        )
    assert sigs == []


def test_probe_url_signal_has_expected_fields() -> None:
    url = "https://target.cocode.dk/search?q=test"
    err_url = "https://target.cocode.dk/search?q=%27"
    responses = {err_url: "warning: mysql_fetch_array()"}
    with _make_client(responses) as client:
        sigs = sqli_tool.probe_url(url, client=client, run_id="r42", observed_at="ts")
    assert sigs[0].tool == "sqli-probe"
    assert sigs[0].run_id == "r42"
    assert sigs[0].asset == "target.cocode.dk"
