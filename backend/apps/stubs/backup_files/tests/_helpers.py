"""Shared test helpers for stub 1.7."""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import httpx


def _resp(
    body: str = "",
    *,
    status_code: int = 200,
    url: str = "https://x.example/",
    content_type: str = "application/octet-stream",
) -> httpx.Response:
    req = httpx.Request("GET", url)
    return httpx.Response(
        status_code=status_code,
        headers={"Content-Type": content_type},
        content=body.encode("utf-8"),
        request=req,
    )


def _mock_get(responses: dict[str, httpx.Response]):
    def side_effect(url, **_kwargs):
        for prefix, resp in responses.items():
            if url == prefix:
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
        "apps.stubs.backup_files.fetcher.httpx.Client"
    ) as mock_client:
        instance = mock_client.return_value.__enter__.return_value
        instance.get.side_effect = (
            get_side_effect
            if get_side_effect is not None
            else _mock_get(responses or {})
        )
        yield instance
