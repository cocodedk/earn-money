"""Unit tests for `_shared/auth/register.register_via_api`."""
from __future__ import annotations

from unittest.mock import MagicMock

import httpx

from apps.stubs._shared.auth.register import register_via_api
from apps.stubs._shared.auth.tests._post_paths_helpers import patch_client


_TARGET = "apps.stubs._shared.auth._post_paths.Client"


def _ok(status: int) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    return r


def test_returns_first_non_404_response() -> None:
    """First candidate path returns 201 → that response wins, no
    further paths tried."""
    queue = [_ok(201), _ok(200)]
    with patch_client(_TARGET, queue):
        resp = register_via_api(
            base_url="https://x.example",
            email="s@example.invalid", password="pw",
        )
    assert resp is not None and resp.status_code == 201
    assert len(queue) == 1


def test_skips_404_and_405_then_returns_next() -> None:
    """First two candidate paths return 404/405, third returns 201 →
    201 returned and remaining queue intact."""
    queue = [_ok(404), _ok(405), _ok(201), _ok(200)]
    with patch_client(_TARGET, queue):
        resp = register_via_api(
            base_url="https://x.example",
            email="s@example.invalid", password="pw",
        )
    assert resp is not None and resp.status_code == 201
    assert len(queue) == 1


def test_all_404_returns_last_404() -> None:
    """No candidate path is registered → last response (404)
    returned so the caller can still inspect it."""
    queue = [_ok(404) for _ in range(64)]
    with patch_client(_TARGET, queue):
        resp = register_via_api(
            base_url="https://x.example",
            email="s@example.invalid", password="pw",
        )
    assert resp is not None and resp.status_code == 404


def test_all_transport_errors_returns_none() -> None:
    """Every candidate path raises a transport error → None returned."""
    queue: list = [httpx.ConnectError("boom") for _ in range(64)]
    with patch_client(_TARGET, queue):
        resp = register_via_api(
            base_url="https://x.example",
            email="s@example.invalid", password="pw",
        )
    assert resp is None


def test_trailing_slash_stripped_from_base_url() -> None:
    """`base_url.rstrip('/')` — the constructed URL must not contain
    a double slash."""
    seen: list[str] = []
    queue = [_ok(201)]
    with patch_client(_TARGET, queue, seen_urls=seen):
        register_via_api(
            base_url="https://x.example/", email="s@example.invalid", password="pw",
        )
    assert "//" not in seen[0].replace("https://", "")
