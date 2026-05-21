"""Shared JSON-API login helper for Phase 2 stubs.

`login_via_api()` is the post-registration "can the new account
actually sign in?" probe used by stubs that need to prove a session
was issued. Tries the candidate login paths in order and returns the
first response that isn't 404/405 — same pattern as
`register_via_api`.

Used today by stub 2.20 (email-verification-bypass). When a third
similar pattern (logout, password-change) appears, the trio is a
candidate for a single parameterised helper.
"""
from __future__ import annotations

import httpx
from httpx import Client

from .endpoints import candidate_login_paths


_DEFAULT_TIMEOUT = 10.0


def login_via_api(
    *, base_url: str, email: str, password: str,
) -> httpx.Response | None:
    """Try the candidate login paths in order. Return the first
    response — whatever its status. None on transport failure for
    every path."""
    last_response: httpx.Response | None = None
    for path in candidate_login_paths():
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
