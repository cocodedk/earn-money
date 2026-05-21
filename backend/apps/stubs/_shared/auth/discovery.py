"""Passive discovery fetch — shared across Phase 2 auth stubs.

`fetch_for_discovery()` does one GET of the target base URL with
no credentials and returns enough metadata for `discover_forms()`
to parse the body. Originally lived under `username_enum/`; lifted
here when stub 2.3 became the second consumer.
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx
from httpx import Client


_DEFAULT_TIMEOUT = 10.0


@dataclass(frozen=True)
class FetchOutcome:
    """Result of the discovery GET. `body` is the response text (empty
    on transport error). `content_type` is the bare media type with no
    charset parameter."""
    ok: bool
    status: int
    body: str
    content_type: str
    final_url: str
    error: str | None


def fetch_for_discovery(base_url: str) -> FetchOutcome:
    """GET ``base_url`` and return enough metadata for
    `discover_forms()` to parse the body."""
    try:
        with Client(
            timeout=_DEFAULT_TIMEOUT,
            follow_redirects=True,
        ) as client:
            response = client.get(base_url)
    except httpx.RequestError as exc:
        return FetchOutcome(
            ok=False, status=0, body="", content_type="",
            final_url=base_url, error=type(exc).__name__,
        )
    content_type = str(
        response.headers.get("content-type", "")
    ).split(";")[0].strip()
    return FetchOutcome(
        ok=True,
        status=response.status_code,
        body=response.text or "",
        content_type=content_type,
        final_url=str(response.url),
        error=None,
    )
