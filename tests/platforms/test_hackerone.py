from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from earn_money.platforms import hackerone


def _mock_transport(fixture_path: Path) -> httpx.MockTransport:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.hackerone.com"
        assert request.url.path == "/v1/hackers/programs/example/structured_scopes"
        assert request.headers["accept"] == "application/json"
        return httpx.Response(200, json=payload)

    return httpx.MockTransport(handler)


def test_fetch_structured_scope_partitions_in_and_oos(fixtures_dir: Path) -> None:
    transport = _mock_transport(fixtures_dir / "hackerone_program_initial.json")
    client = hackerone.Client(
        username="bb-research", token="hai_test", transport=transport
    )
    in_scope, out_of_scope = client.fetch_structured_scope("example")
    assert in_scope == ["*.example.com", "api.example.org"]
    assert out_of_scope == ["blog.example.com"]


def test_fetch_raises_on_non_200(fixtures_dir: Path) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"errors": [{"title": "Forbidden"}]})

    transport = httpx.MockTransport(handler)
    client = hackerone.Client(
        username="bb-research", token="hai_test", transport=transport
    )
    with pytest.raises(hackerone.HackerOneAPIError):
        client.fetch_structured_scope("example")


def test_missing_credentials_raises() -> None:
    with pytest.raises(hackerone.HackerOneAPIError):
        hackerone.Client(username="", token="")
