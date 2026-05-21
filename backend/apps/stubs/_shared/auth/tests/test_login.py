"""Unit tests for `_shared/auth/login.login_via_api`."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from apps.stubs._shared.auth.login import login_via_api


def _patch_client(post_queue: list, *, seen_urls: list | None = None):
    """Patch Client so each `with Client(...) as c: c.post(url, ...)`
    pulls the next result from the shared queue."""
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

    return patch("apps.stubs._shared.auth.login.Client", _FakeClient)


def _ok(status: int) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    return r


def test_returns_first_non_404_response() -> None:
    queue = [_ok(200), _ok(401)]
    with _patch_client(queue):
        resp = login_via_api(
            base_url="https://x.example",
            email="s@example.invalid", password="pw",
        )
    assert resp is not None and resp.status_code == 200
    assert len(queue) == 1  # second path not consumed


def test_skips_404_and_405_then_returns_next() -> None:
    queue = [_ok(404), _ok(405), _ok(401), _ok(200)]
    with _patch_client(queue):
        resp = login_via_api(
            base_url="https://x.example",
            email="s@example.invalid", password="pw",
        )
    assert resp is not None and resp.status_code == 401  # next non-404/405
    assert len(queue) == 1


def test_all_404_returns_last_404() -> None:
    queue = [_ok(404) for _ in range(64)]
    with _patch_client(queue):
        resp = login_via_api(
            base_url="https://x.example",
            email="s@example.invalid", password="pw",
        )
    assert resp is not None and resp.status_code == 404


def test_all_transport_errors_returns_none() -> None:
    queue: list = [httpx.ConnectError("boom") for _ in range(64)]
    with _patch_client(queue):
        resp = login_via_api(
            base_url="https://x.example",
            email="s@example.invalid", password="pw",
        )
    assert resp is None


def test_trailing_slash_stripped() -> None:
    seen: list[str] = []
    queue = [_ok(200)]
    with _patch_client(queue, seen_urls=seen):
        login_via_api(
            base_url="https://x.example/", email="s@example.invalid", password="pw",
        )
    assert "//" not in seen[0].replace("https://", "")
