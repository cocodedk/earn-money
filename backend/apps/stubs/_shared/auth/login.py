"""Shared JSON-API login helper for Phase 2 stubs.

`login_via_api()` is the post-registration "can the new account
actually sign in?" probe used by stubs that need to prove a session
was issued. Tries the candidate login paths in order and returns the
first non-404/405 response. Composes `_post_paths._try_paths`.
"""
from __future__ import annotations

import httpx

from ._post_paths import _try_paths
from .endpoints import candidate_login_paths


def login_via_api(
    *, base_url: str, email: str, password: str,
) -> httpx.Response | None:
    """Try the candidate login paths in order."""
    return _try_paths(
        base_url=base_url,
        paths=candidate_login_paths(),
        body={"email": email, "password": password},
    )
