"""Shared mocking helpers for stub 1.4 fetcher tests."""
from __future__ import annotations

from unittest.mock import patch

import httpx
from contextlib import contextmanager


def _resp(
    body: str = "",
    *,
    status_code: int = 200,
    url: str = "https://x.example/",
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    req = httpx.Request("GET", url)
    return httpx.Response(
        status_code=status_code,
        headers=headers or {},
        content=body.encode("utf-8"),
        request=req,
    )


def _mock_get(responses: dict[str, httpx.Response]):
    """Map URL → response. The 404 probe URL contains a random nonce,
    so any url containing __scanner_backend_hint_404 matches an entry
    keyed by that prefix."""
    def side_effect(url, **_kwargs):
        for prefix, resp in responses.items():
            if url == prefix:
                return resp
            if (
                "__scanner_backend_hint_404" in prefix
                and "__scanner_backend_hint_404" in url
            ):
                return resp
        raise AssertionError(f"unmocked URL: {url}")  # pragma: no cover  # defensive guard
    return side_effect


@contextmanager
def mocked_fetcher(
    responses: dict[str, httpx.Response] | None = None,
    *,
    get_side_effect=None,
):
    with patch(
        "apps.stubs.backend_hints.fetcher.httpx.Client"
    ) as mock_client:
        instance = mock_client.return_value.__enter__.return_value
        instance.get.side_effect = (
            get_side_effect
            if get_side_effect is not None
            else _mock_get(responses or {})
        )
        yield instance
