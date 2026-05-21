"""MFA-bypass submit helpers for stub 2.10.

`enroll_mfa()` flips the canary's MFA flag (POSTs to the candidate
enrollment paths). `post_sensitive_action()` is the load-bearing
probe: it hits the sensitive-action candidate paths with ONLY a
session bearer — no MFA step-up header — so a 2xx response means
the target lets the action through despite MFA enrollment.
"""
from __future__ import annotations

import httpx
from httpx import Client


_DEFAULT_TIMEOUT = 10.0
_ENROLL_PATHS: tuple[str, ...] = (
    "/mfa/enroll",
    "/api/mfa/enroll",
    "/account/mfa/enable",
    "/api/account/mfa",
    "/security/mfa/enroll",
)
_SENSITIVE_PATHS: tuple[str, ...] = (
    "/sensitive-action",
    "/api/sensitive-action",
    "/account/security",
    "/api/account/security",
    "/admin/promote",
    "/api/admin/promote",
)


def _post_with_bearer(
    *, base_url: str, paths: tuple[str, ...], bearer_token: str,
) -> httpx.Response | None:
    """Try each candidate path with `Authorization: Bearer <token>`
    and an empty JSON body. Return the first non-404/405 response.
    None on transport failure for every path."""
    last: httpx.Response | None = None
    headers = {
        "authorization": f"Bearer {bearer_token}",
        "content-type": "application/json",
    }
    for path in paths:
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


def enroll_mfa(
    *, base_url: str, bearer_token: str,
) -> httpx.Response | None:
    """POST to a candidate MFA-enrollment path. Return the first
    non-404/405 response."""
    return _post_with_bearer(
        base_url=base_url, paths=_ENROLL_PATHS,
        bearer_token=bearer_token,
    )


def post_sensitive_action(
    *, base_url: str, bearer_token: str,
) -> httpx.Response | None:
    """POST to a candidate sensitive-action path with no MFA
    step-up header. Return the first non-404/405 response."""
    return _post_with_bearer(
        base_url=base_url, paths=_SENSITIVE_PATHS,
        bearer_token=bearer_token,
    )
