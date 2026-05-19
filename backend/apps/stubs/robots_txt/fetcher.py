"""HTTP fetcher for stub 1.11 — single GET /robots.txt with manual
same-origin redirect handling.

Why manual redirects? Spec §Detection logic rule 7 requires
classifying redirect chain edges ourselves (cross-origin blocked vs
limit exceeded vs same-origin followed). httpx's built-in
`follow_redirects=True` either chases everything or stops at the
first redirect — neither matches the spec. So the fetcher follows
explicitly: cap at `max_redirects`, refuse cross-origin Location,
and surface the outcome via `FetchOutcome.kind`.

Bodies are truncated to `max_body_bytes` (spec default 262144).
Headers are not captured in the bundle by MVP — the classifier
only needs status + body. If a future slice needs response
headers for evidence, surface them here.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/11-robots-txt.md
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

from .classify import FetchOutcome


DEFAULT_VERIFY = os.environ.get("ROBOTS_TXT_VERIFY", "1") != "0"
DEFAULT_TIMEOUT = 5.0  # Spec §Inputs: timeout_ms default 5000

_REDIRECT_STATUSES = {301, 302, 303, 307, 308}


@dataclass(frozen=True)
class FetcherConfig:
    max_body_bytes: int = 262144
    max_redirects: int = 2

    def __post_init__(self) -> None:
        if self.max_body_bytes < 0:
            raise ValueError(
                f"max_body_bytes must be >= 0; got {self.max_body_bytes}"
            )
        if self.max_redirects < 0:
            raise ValueError(
                f"max_redirects must be >= 0; got {self.max_redirects}"
            )


_DEFAULT_CONFIG = FetcherConfig()


def fetch_robots(
    base_url: str, config: FetcherConfig | None = None,
) -> FetchOutcome:
    """Return a FetchOutcome describing what we saw at
    `{base_url}/robots.txt`. Same-origin redirects up to
    `max_redirects` are followed; cross-origin Location yields
    `cross_origin_blocked`."""
    config = config or _DEFAULT_CONFIG
    url = urljoin(base_url + "/", "/robots.txt")
    base_origin = _origin(base_url)
    redirected = False

    with httpx.Client(
        timeout=DEFAULT_TIMEOUT,
        # Spec §Detection logic step 5: follow at most max_redirects.
        # We follow manually so each hop can be vetted for origin.
        follow_redirects=False,
        verify=DEFAULT_VERIFY,
    ) as client:
        for hop in range(config.max_redirects + 1):
            try:
                response = client.get(url)
            except httpx.TransportError:
                return FetchOutcome(
                    kind="unreachable", status=None, body="",
                    final_url=url,
                )

            if response.status_code not in _REDIRECT_STATUSES:
                return _ok_outcome(
                    response=response,
                    final_url=url,
                    redirected=redirected,
                    max_body_bytes=config.max_body_bytes,
                )

            location = response.headers.get("location")
            if not location:
                # Malformed 3xx — classify as the raw status; the
                # classifier maps it through the client_error path.
                return _ok_outcome(
                    response=response,
                    final_url=url,
                    redirected=redirected,
                    max_body_bytes=config.max_body_bytes,
                )

            next_url = urljoin(url, location)
            if _origin(next_url) != base_origin:
                return FetchOutcome(
                    kind="cross_origin_blocked", status=None, body="",
                    final_url=next_url,
                )
            if hop == config.max_redirects:
                return FetchOutcome(
                    kind="redirect_limit", status=None, body="",
                    final_url=next_url,
                )
            url = next_url
            redirected = True

    # Unreachable in practice — the loop always returns. Defensive
    # fallback for type-checkers.
    return FetchOutcome(  # pragma: no cover
        kind="unreachable", status=None, body="", final_url=url,
    )


def _ok_outcome(
    *,
    response: httpx.Response,
    final_url: str,
    redirected: bool,
    max_body_bytes: int,
) -> FetchOutcome:
    return FetchOutcome(
        kind="ok",
        status=response.status_code,
        body=(response.text or "")[:max_body_bytes],
        final_url=final_url,
        redirected=redirected,
    )


def _origin(url: str) -> str:
    """Return `scheme://netloc` for `url` — the RFC 6454 origin in
    string form. Used to compare base_url against each redirect
    Location."""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"
