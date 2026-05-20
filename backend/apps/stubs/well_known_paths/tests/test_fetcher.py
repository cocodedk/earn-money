"""Fetcher contract for stub `well_known_paths`.

HEAD-first probe + Range-bounded GET + same-origin redirect guard.
Specs 21/23/24/25 mandate "do not download full files."

Spec sources: 1.20-1.25 §Inputs + §Safety.
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import httpx

from apps.stubs.well_known_paths.fetcher import fetch_response


@contextmanager
def _mock_client(head_handler, get_handler):
    with patch("apps.stubs.well_known_paths.fetcher.httpx.Client") as mc:
        instance = mc.return_value.__enter__.return_value
        instance.head.side_effect = head_handler
        instance.get.side_effect = get_handler
        yield instance


def _r(status: int, *, url: str = "https://x.example/.env",
       body: bytes = b"", content_type: str = "text/plain") -> httpx.Response:
    return httpx.Response(
        status_code=status,
        headers={"content-type": content_type},
        content=body,
        request=httpx.Request("HEAD", url),
    )


def test_head_404_skips_get() -> None:
    head_calls = {"n": 0}

    def head(url, **_):
        head_calls["n"] += 1
        return _r(404, url=str(url))

    def get(url, **_):  # pragma: no cover — HEAD 404 must short-circuit before GET
        return _r(200, url=str(url), body=b"unused")

    with _mock_client(head, get):
        snap = fetch_response("https://x.example/.env", max_bytes=65536)

    assert head_calls["n"] == 1
    assert snap.status == 404
    assert snap.body == b""


def test_head_200_then_get_with_range() -> None:
    range_headers: list[str] = []

    def head(url, **_):
        return _r(200, url=str(url))

    def get(url, *, headers, **_):
        range_headers.append(headers.get("Range", ""))
        return _r(200, url=str(url), body=b"DB_PASSWORD=secret\nAPI_KEY=abc")

    with _mock_client(head, get):
        snap = fetch_response("https://x.example/.env", max_bytes=65536)

    assert range_headers == ["bytes=0-65535"]
    assert snap.status == 200
    assert b"DB_PASSWORD" in snap.body
    assert snap.head_supported is True


def test_head_unsupported_falls_through_to_get() -> None:
    def head(url, **_):
        return _r(405, url=str(url))

    def get(url, **_):
        return _r(200, url=str(url), body=b"DB_PASSWORD=x")

    with _mock_client(head, get):
        snap = fetch_response("https://x.example/.env", max_bytes=65536)

    assert snap.head_supported is False
    assert snap.status == 200


def test_head_cross_origin_redirect_rejected() -> None:
    def head(url, **_):
        return _r(200, url="https://attacker.example/login")

    def get(url, **_):  # pragma: no cover — HEAD redirect short-circuits before GET
        return _r(200, url=str(url), body=b"unused")

    with _mock_client(head, get):
        snap = fetch_response("https://x.example/.env", max_bytes=65536)

    assert snap.status == 0  # rejected as out-of-origin
    assert snap.body == b""


def test_get_cross_origin_redirect_rejected() -> None:
    """HEAD same-origin but GET redirects to attacker.example."""
    def head(url, **_):
        return _r(200, url=str(url))

    def get(url, **_):
        return _r(200, url="https://attacker.example/leak", body=b"x")

    with _mock_client(head, get):
        snap = fetch_response("https://x.example/.env", max_bytes=65536)

    assert snap.status == 0
    assert snap.body == b""


def test_transport_error_returns_empty_snapshot() -> None:
    def head(url, **_):
        raise httpx.TransportError("connection refused")

    def get(url, **_):  # pragma: no cover
        return _r(200, url=str(url))

    with _mock_client(head, get):
        snap = fetch_response("https://x.example/.env", max_bytes=65536)

    assert snap.status == 0
    assert snap.body == b""
