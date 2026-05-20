"""Shared httpx mock helpers for stub 1.15 fetcher tests.

Each test passes the full URL explicitly to ``resp(url=...)`` so the
mock can match by suffix and return the response as-is — no
post-construction stamping needed.
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import httpx


def resp(
    body: str | bytes = "",
    *,
    status_code: int = 200,
    url: str,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Fake httpx.Response. ``body`` accepts str (UTF-8-encoded for
    the wire) or bytes (passed through) so byte-semantic tests can
    drive the fetcher with raw multibyte payloads."""
    content = body.encode("utf-8") if isinstance(body, str) else body
    return httpx.Response(
        status_code=status_code,
        headers=headers or {},
        content=content,
        request=httpx.Request("GET", url),
    )


def _mock_get(responses: dict[str, httpx.Response]):
    ordered = sorted(responses.items(), key=lambda kv: -len(kv[0]))

    def side_effect(url, **_kwargs):
        url_str = str(url)
        for suffix, response in ordered:
            if url_str.endswith(suffix):
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
        "apps.stubs.public_javascript_bundles.fetcher.httpx.Client"
    ) as mock_client:
        instance = mock_client.return_value.__enter__.return_value
        instance.get.side_effect = (
            get_side_effect
            if get_side_effect is not None
            else _mock_get(responses or {})
        )
        yield instance
