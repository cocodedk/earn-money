"""Reset-completion POST helper for stub 2.6.

Submits the token-bearing `/reset-password` request to the target.
Used twice per scan: first consumption (expected 2xx), then a
reuse probe with the same token (Finding fires if also 2xx).
"""
from __future__ import annotations

import httpx
from httpx import Client

from apps.stubs._shared.auth.requests import SCANNER_USER_AGENT


_DEFAULT_TIMEOUT = 10.0
# Common reset-completion endpoint paths. Matches what canonical
# vuln targets (reset-canary, generic OWASP-style apps) expose.
_RESET_PATHS: tuple[str, ...] = (
    "/reset-password",
    "/api/reset-password",
    "/account/reset",
    "/auth/reset",
)


def complete_reset(
    *, base_url: str, token: str, password: str,
) -> httpx.Response | None:
    """Try the candidate reset-completion paths in order. Return the
    first response whose status is not 404/405. None on transport
    failure for every path."""
    last: httpx.Response | None = None
    headers = {
        "user-agent": SCANNER_USER_AGENT,
        "content-type": "application/json",
    }
    for path in _RESET_PATHS:
        url = base_url.rstrip("/") + path
        try:
            with Client(
                timeout=_DEFAULT_TIMEOUT, follow_redirects=False,
            ) as client:
                resp = client.post(
                    url, headers=headers,
                    json={"token": token, "password": password},
                )
        except httpx.RequestError:
            continue
        last = resp
        if resp.status_code in (404, 405):
            continue
        return resp
    return last
