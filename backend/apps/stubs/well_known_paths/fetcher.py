"""HTTP fetcher for stub `well_known_paths`.

HEAD-first probe per specs 21/23/24/25 ("do not download full files").
If HEAD reports 200/206 OR HEAD is unsupported (405/501) we follow up
with a `Range: bytes=0-N` GET. Same-origin one-hop redirect policy.

Body cap depends on the family the candidate path is in:
* archives / db-dumps → 4096 bytes (magic-byte read only)
* env / git-text / config / logs → 65536 bytes

Returns a `ResponseSnapshot` the classifier consumes directly.

Spec sources: 1.20-1.25 §Inputs + §Safety.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx


DEFAULT_VERIFY = os.environ.get("WELL_KNOWN_PATHS_VERIFY", "1") != "0"

_TIMEOUT_SECONDS = 10.0
_MAX_REDIRECTS = 1  # same-origin one-hop per spec §Safety


@dataclass(frozen=True)
class ResponseSnapshot:
    """`status=0` marks a transport failure or out-of-origin redirect;
    the runner records the miss but skips classifier."""
    status: int
    body: bytes
    final_url: str
    content_type: str
    head_supported: bool


def _same_origin(a: str, b: str) -> bool:
    pa, pb = urlsplit(a), urlsplit(b)
    return (pa.scheme, pa.hostname, pa.port) == (pb.scheme, pb.hostname, pb.port)


def fetch_response(url: str, *, max_bytes: int) -> ResponseSnapshot:
    """HEAD → GET-with-Range flow. Empty body on failure."""
    try:
        with httpx.Client(
            timeout=_TIMEOUT_SECONDS,
            follow_redirects=True,
            max_redirects=_MAX_REDIRECTS,
            verify=DEFAULT_VERIFY,
        ) as client:
            head = client.head(url)
            head_supported = head.status_code not in (405, 501)
            if head_supported and head.status_code >= 400:
                # HEAD said "no such resource" — skip GET.
                return _snapshot(head, b"", head_supported=True)
            if not _same_origin(url, str(head.url)):
                return ResponseSnapshot(
                    status=0, body=b"", final_url=str(head.url),
                    content_type="", head_supported=head_supported,
                )
            resp = client.get(url, headers={"Range": f"bytes=0-{max_bytes - 1}"})
    except (httpx.TransportError, httpx.TooManyRedirects):
        return ResponseSnapshot(
            status=0, body=b"", final_url=url,
            content_type="", head_supported=False,
        )
    if not _same_origin(url, str(resp.url)):
        return ResponseSnapshot(
            status=0, body=b"", final_url=str(resp.url),
            content_type="", head_supported=head_supported,
        )
    body = (resp.content or b"")[:max_bytes]
    return _snapshot(resp, body, head_supported=head_supported)


def _snapshot(resp: httpx.Response, body: bytes, *, head_supported: bool) -> ResponseSnapshot:
    raw_ct = resp.headers.get("content-type", "")
    return ResponseSnapshot(
        status=resp.status_code,
        body=body,
        final_url=str(resp.url),
        content_type=raw_ct.split(";", 1)[0].strip().lower(),
        head_supported=head_supported,
    )
