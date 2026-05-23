"""Shared test utilities for stub runner tests.

Underscore prefix marks it as test-internal — production code MUST NOT
import this module.
"""
from __future__ import annotations

import httpx


def make_cookie_resp(cookies: list[str], status: int = 200) -> httpx.Response:
    """Build an httpx.Response with one or more Set-Cookie headers."""
    raw = [(b"set-cookie", c.encode()) for c in cookies]
    raw.append((b"content-type", b"application/json"))
    return httpx.Response(status, headers=httpx.Headers(raw))
