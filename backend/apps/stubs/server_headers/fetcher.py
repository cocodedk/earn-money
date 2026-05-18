"""HTTP fetcher for stub 1.2 server-headers.

Spec §Request strategy: HEAD / first, fall back to GET / on 405/501,
on an empty header set, or on transport error. Redirects are followed
within httpx's defaults; .history carries each hop for evidence.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/02-server-headers.md
"""
from __future__ import annotations

import os
from typing import Any

import httpx


DEFAULT_TIMEOUT = 10.0
DEFAULT_VERIFY = os.environ.get("SERVER_HEADERS_VERIFY", "1") != "0"

_FALLBACK_STATUS_CODES = {405, 501}


def fetch_evidence(base_url: str) -> dict[str, Any]:
    """Return one evidence bundle for the target's root.

    Shape:
        {
          "method": "HEAD" | "GET",
          "status_code": int,
          "headers": dict[str, str],
          "url": str,
          "redirect_chain": list[{status_code, headers, url}],
        }
    """
    with httpx.Client(
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
        verify=DEFAULT_VERIFY,
    ) as client:
        head_resp = _try_head(client, base_url)
        if _should_fallback(head_resp):
            response = client.get(base_url)
            return _to_bundle(response, "GET")
        return _to_bundle(head_resp, "HEAD")


def _try_head(client: httpx.Client, base_url: str) -> httpx.Response | None:
    try:
        return client.head(base_url)
    except httpx.TransportError:
        return None


def _should_fallback(head_resp: httpx.Response | None) -> bool:
    if head_resp is None:
        return True
    if head_resp.status_code in _FALLBACK_STATUS_CODES:
        return True
    if not dict(head_resp.headers):
        return True
    return False


def _to_bundle(response: httpx.Response, method: str) -> dict[str, Any]:
    return {
        "method": method,
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "url": str(response.url),
        "redirect_chain": [
            {
                "status_code": hop.status_code,
                "headers": dict(hop.headers),
                "url": str(hop.url),
            }
            for hop in getattr(response, "history", ())
        ],
    }
