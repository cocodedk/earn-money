"""Shared registration-POST helper for Phase 2 stubs.

`register_via_api()` tries the candidate paths from
`candidate_register_paths()` in order and returns the first
non-404/405 response. Returns None on transport failure for all
paths. Composes `_post_paths._try_paths`.
"""
from __future__ import annotations

import httpx

from ._post_paths import _try_paths
from .endpoints import candidate_register_paths


def register_via_api(
    *, base_url: str, email: str, password: str,
) -> httpx.Response | None:
    """Try the candidate register paths in order."""
    return _try_paths(
        base_url=base_url,
        paths=candidate_register_paths(),
        body={"email": email, "password": password},
    )
