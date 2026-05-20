"""Shared mocking helpers for stub 1.6 fetcher tests."""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import httpx


def _resp(
    body: str = "",
    *,
    status_code: int = 200,
    url: str = "https://x.example/",
) -> httpx.Response:
    req = httpx.Request("GET", url)
    return httpx.Response(
        status_code=status_code,
        content=body.encode("utf-8"),
        request=req,
    )


def _mock_get(responses: dict[str, httpx.Response]):
    """Map path-suffix → response. Soft-404 probes share a stable
    `scanner_nonexistent` substring so the test maps any nonce instance
    to the same response."""
    def side_effect(url, **_kwargs):
        for prefix, resp in responses.items():
            if "scanner_nonexistent" in prefix and "scanner_nonexistent" in url:
                return resp
            if url.endswith(prefix):
                return resp
        return _resp("", status_code=404, url=url)
    return side_effect


@contextmanager
def mocked_fetcher(
    responses: dict[str, httpx.Response] | None = None,
    *,
    get_side_effect=None,
):
    with patch(
        "apps.stubs.hidden_routes.fetcher.httpx.Client"
    ) as mock_client:
        instance = mock_client.return_value.__enter__.return_value
        instance.get.side_effect = (
            get_side_effect
            if get_side_effect is not None
            else _mock_get(responses or {})
        )
        yield instance
