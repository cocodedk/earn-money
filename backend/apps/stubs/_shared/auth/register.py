"""Shared registration-POST helper for Phase 2 stubs.

`register_via_api()` tries the candidate paths from
`candidate_register_paths()` in order and returns the first
non-404/405 response. Returns None on transport failure for all
paths.

Originally lived under `duplicate_account_confusion/`; lifted here
when stub 2.2 (weak-password-policy) became the second consumer.
"""
from __future__ import annotations

import httpx
from httpx import Client

from .endpoints import candidate_register_paths


_DEFAULT_TIMEOUT = 10.0


def register_via_api(
    *, base_url: str, email: str, password: str,
) -> httpx.Response | None:
    """Try the candidate paths in order. Return the first response —
    whatever its status. None on transport failure for all paths."""
    last_response: httpx.Response | None = None
    for path in candidate_register_paths():
        url = base_url.rstrip("/") + path
        try:
            with Client(
                timeout=_DEFAULT_TIMEOUT, follow_redirects=False,
            ) as client:
                resp = client.post(
                    url,
                    json={"email": email, "password": password},
                    headers={"content-type": "application/json"},
                )
        except httpx.RequestError:
            continue
        last_response = resp
        if resp.status_code in (404, 405):
            continue
        return resp
    return last_response
