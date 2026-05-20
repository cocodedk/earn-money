"""Thin HTTP fetcher for stub 1.16 — single GET + body cap.

Stack-trace detection is content-blind at the HTTP layer (HTML,
JSON, XML, plain text all qualify), so this fetcher doesn't carry
the JS-allowlist that the 1.15 bundle fetcher does. Returns a
ResponseSnapshot the matcher + classifier can consume directly.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/16-stack-traces.md
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import httpx


DEFAULT_VERIFY = os.environ.get("STACK_TRACES_VERIFY", "1") != "0"

_MAX_BODY_BYTES = 262_144  # spec §config default
_TIMEOUT_SECONDS = 10.0
_MAX_REDIRECTS = 3


@dataclass(frozen=True)
class ResponseSnapshot:
    """Status 0 marks a transport failure; the runner records the
    miss as Evidence but skips matcher/classifier (body is empty)."""
    status: int
    body: str
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
        return ResponseSnapshot(status=0, body="", final_url=url, content_type="")
    raw_ct = response.headers.get("content-type", "")
    return ResponseSnapshot(
        status=response.status_code,
        body=(response.text or "")[:_MAX_BODY_BYTES],
        final_url=str(response.url),
        content_type=raw_ct.split(";", 1)[0].strip().lower(),
    )
