"""Shared httpx mock helpers for stub 1.14 fetcher tests."""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import httpx


def resp(
    body: str = "",
    *,
    status_code: int = 200,
    url: str | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Build a fake httpx response. ``url=None`` is a sentinel meaning
    "use the URL the fetcher actually requested" — the mock dispatch
    layer fills it in. That keeps the response's ``final_url`` same-
    origin with the runner's base by default; tests only need to set
    ``url=`` when simulating an off-host redirect."""
    req = httpx.Request("GET", url or "https://placeholder.test/")
    return httpx.Response(
        status_code=status_code,
        headers=headers or {},
        content=body.encode("utf-8"),
        request=req,
    )


def _stamp_url(response: httpx.Response, url: str) -> httpx.Response:
    """Bind the response to the requested URL so ``response.url``
    matches what the fetcher asked for."""
    response._request = httpx.Request("GET", url)
    return response


def _mock_get(responses: dict[str, httpx.Response]):
    """Map URL-suffix → response. Sorted longest-first so a specific
    probe doesn't get shadowed by a shorter suffix."""
    ordered = sorted(responses.items(), key=lambda kv: -len(kv[0]))

    def side_effect(url, **_kwargs):
        url_str = str(url)
        for suffix, response in ordered:
            if url_str.endswith(suffix):
                if response.request.url.host == "placeholder.test":
                    return _stamp_url(response, url_str)
                return response
        return resp("", status_code=404, url=url_str)
    return side_effect


@contextmanager
def mocked_fetcher(
    responses: dict[str, httpx.Response] | None = None,
    *,
    get_side_effect=None,
):
    with patch(
        "apps.stubs.source_maps.fetcher.httpx.Client"
    ) as mock_client:
        instance = mock_client.return_value.__enter__.return_value
        instance.get.side_effect = (
            get_side_effect
            if get_side_effect is not None
            else _mock_get(responses or {})
        )
        yield instance
