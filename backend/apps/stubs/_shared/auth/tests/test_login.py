"""Unit tests for `_shared/auth/login.login_via_api`."""
from __future__ import annotations

from unittest.mock import MagicMock

import httpx

from apps.stubs._shared.auth.login import login_via_api
from apps.stubs._shared.auth.tests._post_paths_helpers import patch_client


_TARGET = "apps.stubs._shared.auth._post_paths.Client"


def _ok(status: int) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    return r


def test_returns_first_non_404_response() -> None:
    queue = [_ok(200), _ok(401)]
    with patch_client(_TARGET, queue):
        resp = login_via_api(
            base_url="https://x.example",
            email="s@example.invalid", password="pw",
        )
    assert resp is not None and resp.status_code == 200
    assert len(queue) == 1


def test_skips_404_and_405_then_returns_next() -> None:
    queue = [_ok(404), _ok(405), _ok(401), _ok(200)]
    with patch_client(_TARGET, queue):
        resp = login_via_api(
            base_url="https://x.example",
            email="s@example.invalid", password="pw",
        )
    assert resp is not None and resp.status_code == 401
    assert len(queue) == 1


def test_all_404_returns_last_404() -> None:
    queue = [_ok(404) for _ in range(64)]
    with patch_client(_TARGET, queue):
        resp = login_via_api(
            base_url="https://x.example",
            email="s@example.invalid", password="pw",
        )
    assert resp is not None and resp.status_code == 404


def test_all_transport_errors_returns_none() -> None:
    queue: list = [httpx.ConnectError("boom") for _ in range(64)]
    with patch_client(_TARGET, queue):
        resp = login_via_api(
            base_url="https://x.example",
            email="s@example.invalid", password="pw",
        )
    assert resp is None


def test_trailing_slash_stripped() -> None:
    seen: list[str] = []
    queue = [_ok(200)]
    with patch_client(_TARGET, queue, seen_urls=seen):
        login_via_api(
            base_url="https://x.example/", email="s@example.invalid", password="pw",
        )
    assert "//" not in seen[0].replace("https://", "")
