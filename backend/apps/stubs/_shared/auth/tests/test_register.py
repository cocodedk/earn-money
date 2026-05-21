"""Unit tests for `_shared/auth/register.register_via_api`."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from apps.stubs._shared.auth.register import register_via_api


def _patch_client(post_queue: list, *, seen_urls: list | None = None):
    """Patch Client so each `with Client(...) as c: c.post(url, ...)`
    pulls the next result from the shared queue. A list of URLs is
    optionally captured for assertion."""
    class _FakeClient:
        def __init__(self, **_kw: object) -> None:
            pass

        def __enter__(self) -> "_FakeClient":
            return self

        def __exit__(self, *_a: object) -> None:
            return None

        def post(self, url: str, **_kw: object):  # type: ignore[no-untyped-def]
            if seen_urls is not None:
                seen_urls.append(url)
            result = post_queue.pop(0)
            if isinstance(result, BaseException):
                raise result
            return result

    return patch("apps.stubs._shared.auth.register.Client", _FakeClient)


def _ok(status: int) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    return r


def test_returns_first_non_404_response() -> None:
    """First candidate path returns 201 → that response wins, no
    further paths tried."""
    queue = [_ok(201), _ok(200)]
    with _patch_client(queue):
        resp = register_via_api(
            base_url="https://x.example",
            email="s@example.invalid", password="pw",
        )
    assert resp is not None and resp.status_code == 201
    assert len(queue) == 1  # second path not consumed


def test_skips_404_and_405_then_returns_next() -> None:
    """First two candidate paths return 404/405, third returns 201 →
    201 returned and remaining queue intact."""
    queue = [_ok(404), _ok(405), _ok(201), _ok(200)]
    with _patch_client(queue):
        resp = register_via_api(
            base_url="https://x.example",
            email="s@example.invalid", password="pw",
        )
    assert resp is not None and resp.status_code == 201
    assert len(queue) == 1


def test_all_404_returns_last_404() -> None:
    """No candidate path is registered → last response (404)
    returned so the caller can still inspect it."""
    n = 64
    queue = [_ok(404) for _ in range(n)]
    with _patch_client(queue):
        resp = register_via_api(
            base_url="https://x.example",
            email="s@example.invalid", password="pw",
        )
    assert resp is not None and resp.status_code == 404


def test_all_transport_errors_returns_none() -> None:
    """Every candidate path raises a transport error → None returned."""
    n = 64
    queue: list = [httpx.ConnectError("boom") for _ in range(n)]
    with _patch_client(queue):
        resp = register_via_api(
            base_url="https://x.example",
            email="s@example.invalid", password="pw",
        )
    assert resp is None


def test_trailing_slash_stripped_from_base_url() -> None:
    """`base_url.rstrip('/')` — the constructed URL must not contain
    a double slash."""
    seen_urls: list[str] = []
    queue = [_ok(201)]
    with _patch_client(queue, seen_urls=seen_urls):
        register_via_api(
            base_url="https://x.example/", email="s@example.invalid", password="pw",
        )
    assert "//" not in seen_urls[0].replace("https://", "")
