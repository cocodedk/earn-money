"""MFA-disable submit helper for stub 2.13.

Posts to candidate MFA-disable endpoints with the session bearer
and NO step-up header / current-password body. A target that
honours the request without challenging the user gets caught by
the post-call `verify_mfa_enrolled` re-check in the runner.
"""
from __future__ import annotations

import httpx
from httpx import Client


_DEFAULT_TIMEOUT = 10.0
_DISABLE_PATHS: tuple[str, ...] = (
    "/mfa/disable",
    "/api/mfa/disable",
    "/account/mfa/disable",
    "/security/mfa/disable",
)


def disable_mfa(
    *, base_url: str, bearer_token: str,
) -> httpx.Response | None:
    """POST to candidate MFA-disable paths. Return the first
    non-404/405 response. None on transport failure for all paths."""
    headers = {
        "authorization": f"Bearer {bearer_token}",
        "content-type": "application/json",
    }
    last: httpx.Response | None = None
    for path in _DISABLE_PATHS:
        url = base_url.rstrip("/") + path
        try:
            with Client(
                timeout=_DEFAULT_TIMEOUT, follow_redirects=False,
            ) as client:
                resp = client.post(url, headers=headers, json={})
        except httpx.RequestError:
            continue
        last = resp
        if resp.status_code in (404, 405):
            continue
        return resp
    return last
