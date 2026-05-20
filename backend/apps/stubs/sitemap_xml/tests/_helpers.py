"""Shared test helpers for stub 1.12."""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import httpx


def resp(
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
    """Map path-suffix → response. Sorted longest-first so a specific
    probe doesn't get shadowed by a shorter suffix."""
    ordered = sorted(responses.items(), key=lambda kv: -len(kv[0]))

    def side_effect(url, **_kwargs):
        for suffix, response in ordered:
            if url.endswith(suffix):
                return response
        return resp("", status_code=404, url=url)
    return side_effect


@contextmanager
def mocked_fetcher(
    responses: dict[str, httpx.Response] | None = None,
    *,
    get_side_effect=None,
):
    with patch(
        "apps.stubs.sitemap_xml.fetcher.httpx.Client"
    ) as mock_client:
        instance = mock_client.return_value.__enter__.return_value
        instance.get.side_effect = (
            get_side_effect
            if get_side_effect is not None
            else _mock_get(responses or {})
        )
        yield instance
