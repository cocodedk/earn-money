"""Internal helper: POST a JSON body to a sequence of candidate
paths, returning the first non-404/405 response.

Used by `_shared/auth/register.py` and `_shared/auth/login.py`. The
underscore prefix marks this as private — consumers should call the
named helpers, not `_try_paths` directly.
"""
from __future__ import annotations

from collections.abc import Iterable

import httpx
from httpx import Client


_DEFAULT_TIMEOUT = 10.0


def _try_paths(
    *, base_url: str, paths: Iterable[str], body: dict,
) -> httpx.Response | None:
    """POST ``body`` (as JSON) to each path in order. Return the first
    response whose status is NOT 404 or 405. If every path returns
    404/405, return the last 404/405 response so the caller can still
    inspect it. None on transport failure for every path."""
    last_response: httpx.Response | None = None
    for path in paths:
        url = base_url.rstrip("/") + path
        try:
            with Client(
                timeout=_DEFAULT_TIMEOUT, follow_redirects=False,
            ) as client:
                resp = client.post(
                    url, json=body,
                    headers={"content-type": "application/json"},
                )
        except httpx.RequestError:
            continue
        last_response = resp
        if resp.status_code in (404, 405):
            continue
        return resp
    return last_response
