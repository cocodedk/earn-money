"""HTTP fetcher for stub 1.19 sql_orm_errors — single GET + body cap.

Mirrors stub 1.16 + 1.17's `fetcher.py`. Body capped at the spec's
`max_body_bytes_to_scan` (262144). Follows redirects within a one-hop
budget on the same origin (sufficient for MVP; full same-origin
redirect policy lift to `_shared/http.py` is deferred per the Phase 1
closeout plan).

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/19-sql-orm-errors.md
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import httpx


DEFAULT_VERIFY = os.environ.get("SQL_ORM_ERRORS_VERIFY", "1") != "0"

_MAX_BODY_BYTES = 262_144  # spec §config default
_TIMEOUT_SECONDS = 10.0
_MAX_REDIRECTS = 1  # spec §Safety: same-origin one-hop


@dataclass(frozen=True)
class ResponseSnapshot:
    """`status=0` marks a transport failure; runner records the miss
    as Evidence but skips matcher/classifier (body is empty)."""
    status: int
    body: bytes
    final_url: str
    content_type: str


def fetch_response(url: str) -> ResponseSnapshot:
    try:
        with httpx.Client(
            timeout=_TIMEOUT_SECONDS,
            follow_redirects=True,
            max_redirects=_MAX_REDIRECTS,
            verify=DEFAULT_VERIFY,
        ) as client:
            response = client.get(url)
    except (httpx.TransportError, httpx.TooManyRedirects):
        return ResponseSnapshot(status=0, body=b"", final_url=url, content_type="")
    raw_ct = response.headers.get("content-type", "")
    body = response.content[:_MAX_BODY_BYTES] if response.content else b""
    return ResponseSnapshot(
        status=response.status_code,
        body=body,
        final_url=str(response.url),
        content_type=raw_ct.split(";", 1)[0].strip().lower(),
    )
