"""HTTP fetcher for stub 1.14 source-maps.

Single unified ``fetch_url`` reused by the runner for HTML, asset,
and ``.map`` GETs. The same FetchOutcome shape feeds the classifier
in slice 6, so all three request layers map onto one closed
``ok/absent/blocked/inconclusive`` kind set per spec §"Source map
fetch".

Cross-host redirect handling: httpx follows redirects up to
``max_redirects``, then we verify the final URL is same-origin
with ``base_origin``. Mismatches degrade to ``inconclusive`` so
the runner never treats an off-host body as evidence.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/14-source-maps.md
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

import httpx

from .._shared.url import origin


DEFAULT_VERIFY = os.environ.get("SOURCE_MAPS_VERIFY", "1") != "0"

_OK_STATUS = 200
_ABSENT_STATUSES = {404, 410}
_BLOCKED_STATUSES = {401, 403}

FetchKind = Literal["ok", "absent", "blocked", "inconclusive"]


@dataclass(frozen=True)
class FetcherConfig:
    """Per-call knobs. Defaults match spec §Inputs."""
    max_body_bytes: int = 2_000_000
    max_redirects: int = 3
    timeout_seconds: float = 10.0


@dataclass(frozen=True)
class FetchOutcome:
    kind: FetchKind
    status: int | None
    body: str
    final_url: str
    content_type: str


_DEFAULT_CONFIG = FetcherConfig()


def fetch_url(
    url: str, base_origin: str, config: FetcherConfig | None = None,
) -> FetchOutcome:
    """GET ``url`` and classify the response into a FetchOutcome.

    ``base_origin`` is the origin (scheme://netloc) the runner trusts;
    a redirect that leaves it degrades to ``inconclusive``. The body
    is truncated to ``config.max_body_bytes`` so a hostile/large
    response can't exhaust memory.
    """
    config = config or _DEFAULT_CONFIG
    with httpx.Client(
        timeout=config.timeout_seconds,
        follow_redirects=True,
        max_redirects=config.max_redirects,
        verify=DEFAULT_VERIFY,
    ) as client:
        try:
            response = client.get(url)
        except (httpx.TransportError, httpx.TooManyRedirects):
            # TooManyRedirects is NOT a TransportError subclass; we
            # cap redirects at 3 so the runtime path IS reachable.
            return FetchOutcome(
                kind="inconclusive", status=None, body="",
                final_url=url, content_type="",
            )
    return _classify(response, base_origin, config.max_body_bytes)


def _classify(
    response: httpx.Response, base_origin: str, max_body_bytes: int,
) -> FetchOutcome:
    final_url = str(response.url)
    content_type = response.headers.get("content-type", "")
    if origin(final_url) != base_origin:
        return FetchOutcome(
            kind="inconclusive", status=response.status_code,
            body="", final_url=final_url, content_type=content_type,
        )
    status = response.status_code
    body = (response.text or "")[:max_body_bytes]
    kind = _kind_for_status(status)
    if kind != "ok":
        # Body discarded for non-200 paths so persistence stays
        # bounded; the status + final_url are enough audit trail.
        body = ""
    return FetchOutcome(
        kind=kind, status=status, body=body,
        final_url=final_url, content_type=content_type,
    )


def _kind_for_status(status: int) -> FetchKind:
    if status == _OK_STATUS:
        return "ok"
    if status in _ABSENT_STATUSES:
        return "absent"
    if status in _BLOCKED_STATUSES:
        return "blocked"
    return "inconclusive"
