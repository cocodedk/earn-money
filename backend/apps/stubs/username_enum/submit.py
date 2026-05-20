"""Stub 2.1 submit helper — sends an `httpx.Request` and returns the
raw response object.

Kept distinct from `fetcher.py` so the submit path can be mocked
independently in tests. The discovery fetcher does a passive GET;
this module fires the active comparison probes.
"""
from __future__ import annotations

import httpx
from httpx import Client


_DEFAULT_TIMEOUT = 10.0


def submit_probe(request: httpx.Request) -> httpx.Response | None:
    """Send ``request`` via a fresh `httpx.Client` (isolated cookie
    jar) and return the response. Returns None on transport error so
    the caller can record `transport_error` without re-raising."""
    try:
        with Client(
            timeout=_DEFAULT_TIMEOUT,
            follow_redirects=False,
        ) as client:
            return client.send(request)
    except httpx.RequestError:
        return None
