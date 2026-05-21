"""Registration-POST helper for stub 2.19.

Tries common JSON registration endpoints (`/api/Users`, `/register`,
`/api/register`, `/api/v1/register`, `/api/auth/register`) in order
and returns the first non-error response. None on transport failure.
"""
from __future__ import annotations

import httpx
from httpx import Client


_REGISTER_PATHS: tuple[str, ...] = (
    "/api/Users",            # Juice Shop
    "/api/register",
    "/api/v1/register",
    "/api/auth/register",
    "/register",
)
_DEFAULT_TIMEOUT = 10.0


def register_via_api(
    *, base_url: str, email: str, password: str,
) -> httpx.Response | None:
    """Try the candidate paths in order. Return the first response —
    whatever its status. None on transport failure for all paths."""
    last_response: httpx.Response | None = None
    for path in _REGISTER_PATHS:
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
        # 404 / 405 → wrong endpoint, try next. Anything else is
        # informative even if it's a 4xx — the runner diffs against
        # a sibling probe.
        if resp.status_code in (404, 405):
            continue
        return resp
    return last_response
