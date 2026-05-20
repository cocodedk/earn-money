"""Thin HTTP fetcher for stub 1.17 — single GET + body cap.

Spec §config: max_response_body_bytes default 65536. Stack-trace
detection (stub 1.16) uses a different cap (262144 / spec §16
max_response_bytes), so this fetcher stays local rather than
cross-importing — keeps the cap visible per-stub.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/17-verbose-api-errors.md
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import httpx


DEFAULT_VERIFY = os.environ.get("VERBOSE_API_ERRORS_VERIFY", "1") != "0"

_MAX_BODY_BYTES = 65_536  # spec §config max_response_body_bytes
_TIMEOUT_SECONDS = 10.0
_MAX_REDIRECTS = 3


@dataclass(frozen=True)
class ResponseSnapshot:
    status: int
    body: str
    final_url: str
    content_type: str
    headers: dict[str, str]  # lowercased header names → value
    body_truncated: bool  # True when raw body exceeded _MAX_BODY_BYTES


def fetch_response(url: str) -> ResponseSnapshot:
    try:
        with httpx.Client(
            timeout=_TIMEOUT_SECONDS,
            follow_redirects=False,  # spec §config follow_redirects=False
            max_redirects=_MAX_REDIRECTS,
            verify=DEFAULT_VERIFY,
        ) as client:
            response = client.get(url)
    except (httpx.TransportError, httpx.TooManyRedirects):
        return ResponseSnapshot(
            status=0, body="", final_url=url, content_type="",
            headers={}, body_truncated=False,
        )
    raw_ct = response.headers.get("content-type", "")
    raw_text = response.text or ""
    return ResponseSnapshot(
        status=response.status_code,
        body=raw_text[:_MAX_BODY_BYTES],
        final_url=str(response.url),
        content_type=raw_ct.split(";", 1)[0].strip().lower(),
        headers={k.lower(): v for k, v in response.headers.items()},
        body_truncated=len(raw_text) > _MAX_BODY_BYTES,
    )
