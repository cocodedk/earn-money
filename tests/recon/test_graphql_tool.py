"""Tests for graphql_tool — introspection probe."""

from __future__ import annotations

import json

import httpx

from earn_money.recon import graphql_tool


def _accept_example_com(host: str) -> bool:
    return host.endswith("example.com")


def _accept_all(_host: str) -> bool:
    return True


def _mock(handler: object) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))  # type: ignore[arg-type]


_INTROSPECTION_OK = json.dumps({
    "data": {
        "__schema": {
            "queryType": {"name": "Query"},
            "types": [
                {"name": "Query"}, {"name": "User"}, {"name": "Mutation"},
            ],
        }
    }
})


def test_build_query_returns_introspection_post_body() -> None:
    body = graphql_tool.build_query()
    assert "__schema" in body["query"]
    assert "types" in body["query"]


def test_probe_emits_signal_on_introspection_enabled() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://api.example.com/graphql":
            return httpx.Response(200, text=_INTROSPECTION_OK)
        return httpx.Response(404)

    with _mock(handler) as client:
        sigs = graphql_tool.probe(
            "https://api.example.com/",
            client=client,
            in_scope=_accept_example_com,
            run_id="r1",
            observed_at="2026-05-14T12:00:00Z",
        )
    assert len(sigs) == 1
    sig = sigs[0]
    assert sig.tool == "graphql-probe"
    assert sig.signal_type == "introspection_enabled"
    assert sig.asset == "api.example.com"
    assert sig.target == "https://api.example.com/graphql"
    assert sig.signature == "graphql|/graphql|introspection"
    payload = json.loads(sig.payload)
    assert payload["severity"] == "medium"
    assert "User" in payload["type_sample"]


def test_probe_no_signal_when_no_endpoint_responds() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)
    with _mock(handler) as client:
        sigs = graphql_tool.probe(
            "https://api.example.com/",
            client=client, in_scope=_accept_example_com,
            run_id="r1", observed_at="t",
        )
    assert sigs == []


def test_probe_no_signal_when_response_is_html() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>Login</html>")
    with _mock(handler) as client:
        sigs = graphql_tool.probe(
            "https://api.example.com/",
            client=client, in_scope=_accept_example_com,
            run_id="r1", observed_at="t",
        )
    assert sigs == []


def test_probe_no_signal_when_data_present_but_schema_missing() -> None:
    """A real GraphQL server with introspection *disabled* returns
    `{"errors":[…]}` or `{"data":null}` — neither should fire."""
    body = json.dumps({"errors": [{"message": "introspection disabled"}]})
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)
    with _mock(handler) as client:
        sigs = graphql_tool.probe(
            "https://api.example.com/",
            client=client, in_scope=_accept_example_com,
            run_id="r1", observed_at="t",
        )
    assert sigs == []


def test_probe_refuses_when_base_host_out_of_scope() -> None:
    """Defense in depth: even if the caller mis-routed, base host
    out-of-scope means zero traffic."""
    seen: list[str] = []
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, text=_INTROSPECTION_OK)
    with _mock(handler) as client:
        sigs = graphql_tool.probe(
            "https://attacker.com/",
            client=client, in_scope=_accept_example_com,
            run_id="r1", observed_at="t",
        )
    assert sigs == []
    assert seen == []  # no requests went out


def test_probe_handles_network_error_silently() -> None:
    def boom(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated")
    with _mock(boom) as client:
        sigs = graphql_tool.probe(
            "https://api.example.com/",
            client=client, in_scope=_accept_all,
            run_id="r1", observed_at="t",
        )
    assert sigs == []


def test_probe_tries_every_common_path() -> None:
    """Each path in COMMON_PATHS gets one POST when in scope."""
    seen: list[str] = []
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(404)
    with _mock(handler) as client:
        graphql_tool.probe(
            "https://api.example.com/",
            client=client, in_scope=_accept_example_com,
            run_id="r1", observed_at="t",
        )
    assert len(seen) == len(graphql_tool.COMMON_PATHS)
    assert "https://api.example.com/graphql" in seen
