"""HTTP fetcher for stub 1.12 — single GET sitemap URL.

Unlike stub 1.11's robots fetcher, this one defers to httpx's
built-in `follow_redirects=True` because spec §Request strategy
rule 5 says "follow redirects using the shared redirect policy"
rather than mandating manual redirect classification. The fetcher
doesn't enforce same-origin on redirect — that's the runner's job
when classifying the final URL.

Body cap drives a `too_large` outcome instead of a silently
truncated body so the classifier can flag the partial read.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/12-sitemap-xml.md
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

from .classify import FetchOutcome


DEFAULT_VERIFY = os.environ.get("SITEMAP_XML_VERIFY", "1") != "0"
DEFAULT_TIMEOUT = 8.0


@dataclass(frozen=True)
class FetcherConfig:
    # Spec §Inputs: max_response_bytes recommended default 2_000_000.
    max_body_bytes: int = 2_000_000

    def __post_init__(self) -> None:
        if self.max_body_bytes < 0:
            raise ValueError(
                f"max_body_bytes must be >= 0; got {self.max_body_bytes}"
            )


_DEFAULT_CONFIG = FetcherConfig()


def fetch_sitemap(
    url: str, config: FetcherConfig | None = None,
) -> FetchOutcome:
    """GET `url` and return a FetchOutcome. `too_large` fires when
    the response body exceeds `max_body_bytes`; the bounded sample
    is still surfaced in `body` so the runner can persist it as
    evidence."""
    config = config or _DEFAULT_CONFIG
    with httpx.Client(
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
        verify=DEFAULT_VERIFY,
    ) as client:
        try:
            response = client.get(url)
        except httpx.TransportError:
            return FetchOutcome(
                kind="unreachable", status=None, body="", final_url=url,
            )

    raw_body = response.text or ""
    body = raw_body[:config.max_body_bytes]
    kind = "too_large" if len(raw_body) > config.max_body_bytes else "ok"
    return FetchOutcome(
        kind=kind,
        status=response.status_code,
        body=body,
        final_url=str(response.url),
    )
