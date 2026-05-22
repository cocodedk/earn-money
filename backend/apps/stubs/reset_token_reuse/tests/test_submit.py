"""Unit tests for `reset_token_reuse.submit.complete_reset`."""
from __future__ import annotations

from unittest.mock import MagicMock

import httpx

from apps.stubs._shared.auth.tests._post_paths_helpers import patch_client
from apps.stubs.reset_token_reuse.submit import complete_reset


_TARGET = "apps.stubs.reset_token_reuse.submit.Client"


def _ok(status: int) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    return r


def test_returns_first_non_404_response() -> None:
    queue = [_ok(200), _ok(200)]
    with patch_client(_TARGET, queue):
        resp = complete_reset(
            base_url="https://x.example", token="t", password="pw",
        )
    assert resp is not None and resp.status_code == 200
    assert len(queue) == 1


def test_skips_404_then_returns_next() -> None:
    queue = [_ok(404), _ok(405), _ok(200), _ok(500)]
    with patch_client(_TARGET, queue):
        resp = complete_reset(
            base_url="https://x.example", token="t", password="pw",
        )
    assert resp is not None and resp.status_code == 200
    assert len(queue) == 1


def test_all_404_returns_last() -> None:
    queue = [_ok(404)] * 4
    with patch_client(_TARGET, queue):
        resp = complete_reset(
            base_url="https://x.example", token="t", password="pw",
        )
    assert resp is not None and resp.status_code == 404


def test_all_transport_errors_returns_none() -> None:
    queue: list = [httpx.ConnectError("boom")] * 4
    with patch_client(_TARGET, queue):
        resp = complete_reset(
            base_url="https://x.example", token="t", password="pw",
        )
    assert resp is None


def test_trailing_slash_stripped() -> None:
    seen: list[str] = []
    queue = [_ok(200)]
    with patch_client(_TARGET, queue, seen_urls=seen):
        complete_reset(
            base_url="https://x.example/", token="t", password="pw",
        )
    assert "//" not in seen[0].replace("https://", "")
