"""Change-email POST helper + bearer-token extractor for stub 2.9.

`change_email_unauthed_password()` fires the load-bearing probe:
authenticated request with a `new_email` payload but NO
`current_password` field. A target that requires re-auth on email
change returns 4xx; a vulnerable target returns 2xx.

`bearer_token_from(response)` parses the login response body for
any common token-shape field. JWT-style strings, opaque hex/base64
tokens, and Juice-Shop-style `{"authentication": {"token": ...}}`
are all covered.
"""
from __future__ import annotations

import json
from typing import Any

import httpx
from httpx import Client


_DEFAULT_TIMEOUT = 10.0
_CHANGE_PATHS: tuple[str, ...] = (
    "/change-email",
    "/api/change-email",
    "/account/email",
    "/api/account/email",
    "/api/users/me",
    "/api/account",
)


def change_email_unauthed_password(
    *, base_url: str, bearer_token: str, new_email: str,
) -> httpx.Response | None:
    """Try each candidate /change-email path with `Authorization:
    Bearer <token>` and a body that contains ONLY `new_email` (no
    current_password). Return the first non-404/405 response. None
    on transport failure for every path."""
    last: httpx.Response | None = None
    headers = {
        "authorization": f"Bearer {bearer_token}",
        "content-type": "application/json",
    }
    for path in _CHANGE_PATHS:
        url = base_url.rstrip("/") + path
        try:
            with Client(
                timeout=_DEFAULT_TIMEOUT, follow_redirects=False,
            ) as client:
                resp = client.post(
                    url, headers=headers,
                    json={"new_email": new_email},
                )
        except httpx.RequestError:
            continue
        last = resp
        if resp.status_code in (404, 405):
            continue
        return resp
    return last


# Common token-shape keys seen across JSON login responses. Order
# matches priority: explicit `token` first, then JWT-style names,
# then framework-specific nested shapes.
_TOKEN_KEY_PRIORITY: tuple[str, ...] = (
    "token", "accessToken", "access_token", "jwt", "id_token",
)


def bearer_token_from(response: httpx.Response) -> str | None:
    """Extract a bearer token from the login response. Falls through
    several common shapes and returns None if nothing recognisable
    appears."""
    try:
        body = response.json()
    except (json.JSONDecodeError, ValueError):
        return None
    return _first_string_under(body, _TOKEN_KEY_PRIORITY)


def _first_string_under(payload: Any, keys: tuple[str, ...]) -> str | None:
    """Bounded recursion (depth 3) over dict payloads looking for
    the first string value at any of ``keys``. Returns None on
    miss. Bounded so a malicious server can't make the parser
    run away."""
    return _walk(payload, keys, depth=0, max_depth=3)


def _walk(node: Any, keys: tuple[str, ...], *, depth: int, max_depth: int) -> str | None:
    if depth > max_depth:
        return None
    if isinstance(node, dict):
        for k in keys:
            v = node.get(k)
            if isinstance(v, str) and v:
                return v
        for v in node.values():
            result = _walk(v, keys, depth=depth + 1, max_depth=max_depth)
            if result is not None:
                return result
    return None
