from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from earn_money.recon import chaos


def test_fetch_returns_normalized_fqdns(fixtures_dir: Path) -> None:
    payload = json.loads((fixtures_dir / "chaos_subdomains.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "dns.projectdiscovery.io"
        assert request.url.path == "/dns/example.com/subdomains"
        assert request.headers["authorization"] == "tkn"
        return httpx.Response(200, json=payload)

    client = chaos.Client(token="tkn", transport=httpx.MockTransport(handler))
    result = client.fetch_subdomains("example.com")

    assert sorted(result) == [
        "api.example.com",
        "auth.example.com",
        "stage.example.com",
        "www.example.com",
    ]


def test_fetch_raises_on_non_200() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    client = chaos.Client(token="tkn", transport=httpx.MockTransport(handler))
    with pytest.raises(chaos.ChaosAPIError):
        client.fetch_subdomains("example.com")


def test_missing_token_raises() -> None:
    with pytest.raises(chaos.ChaosAPIError):
        chaos.Client(token="")


def test_fetch_handles_empty_response() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"domain": "example.com", "subdomains": []})

    client = chaos.Client(token="tkn", transport=httpx.MockTransport(handler))
    assert client.fetch_subdomains("example.com") == []


def test_client_supports_context_manager() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"domain": "example.com", "subdomains": []})

    with chaos.Client(token="tkn", transport=httpx.MockTransport(handler)) as client:
        assert client.fetch_subdomains("example.com") == []


def test_network_error_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connect refused")

    client = chaos.Client(token="tkn", transport=httpx.MockTransport(handler))
    with pytest.raises(chaos.ChaosAPIError) as excinfo:
        client.fetch_subdomains("example.com")
    assert "Network error" in str(excinfo.value)


def test_non_json_body_wrapped() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>gateway error</html>")

    client = chaos.Client(token="tkn", transport=httpx.MockTransport(handler))
    with pytest.raises(chaos.ChaosAPIError) as excinfo:
        client.fetch_subdomains("example.com")
    assert "non-JSON" in str(excinfo.value)


def test_full_fqdn_in_response_is_handled() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"domain": "example.com", "subdomains": ["api.example.com", "auth"]},
        )

    client = chaos.Client(token="tkn", transport=httpx.MockTransport(handler))
    result = client.fetch_subdomains("example.com")
    assert sorted(result) == ["api.example.com", "auth.example.com"]
