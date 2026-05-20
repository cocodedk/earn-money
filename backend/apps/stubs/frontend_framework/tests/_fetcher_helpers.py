"""Shared mocking helpers for stub 1.3 fetcher tests.

Underscore-prefixed module — test-internal, not part of the package's
public API. Each test file imports `mocked_fetcher` plus `_resp` to
build canned httpx.Response objects keyed by URL.
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import httpx


def _resp(
    body: str,
    *,
    status_code: int = 200,
    url: str = "https://x.example/",
    content_type: str = "text/html",
) -> httpx.Response:
    req = httpx.Request("GET", url)
    return httpx.Response(
        status_code=status_code,
        headers={"Content-Type": content_type},
        content=body.encode("utf-8"),
        request=req,
    )


def _mock_client(responses: dict[str, httpx.Response]):
    """Map URL → mocked response. Unmocked URLs raise so test bugs are loud."""
    def side_effect(url, **_kwargs):
        if url in responses:
            return responses[url]
        raise AssertionError(f"unmocked URL: {url}")  # pragma: no cover  # defensive guard
    return side_effect


@contextmanager
def mocked_fetcher(responses: dict[str, httpx.Response] | None = None, *, get_side_effect=None):
    """Patch the fetcher's httpx.Client. Tests pass either a {url: response}
    map OR an explicit side_effect callable (e.g., one that raises
    TransportError). Inside the block, fetch_evidence() runs against
    the mocks instead of the network."""
    with patch(
        "apps.stubs.frontend_framework.fetcher.httpx.Client"
    ) as mock_client:
        instance = mock_client.return_value.__enter__.return_value
        if get_side_effect is not None:
            instance.get.side_effect = get_side_effect
        else:
            instance.get.side_effect = _mock_client(responses or {})
        yield instance
