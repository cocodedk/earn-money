"""HTTP fetcher for stub 1.13 security.txt.

Single GET per candidate path with httpx's built-in redirect
follower. The fetcher classifies the response into a FetchKind
(ok / absent / blocked / inconclusive) so the classifier composes
verdicts without duplicating status-to-kind logic.

Cross-host redirect handling: the spec allows same-host follows
but rejects cross-host. The simplest correct shape is to let
httpx follow redirects and then verify the final URL is same-
origin as the base; mismatches yield `inconclusive`. This matches
the spec's "redirect to a different registrable domain" disallowed
behaviour while keeping the fetcher loop simple.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/13-security-txt.md
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from .._shared.url import origin
from .classify import FetchOutcome


DEFAULT_VERIFY = os.environ.get("SECURITY_TXT_VERIFY", "1") != "0"
DEFAULT_TIMEOUT = 5.0  # Spec §Inputs: timeout_seconds default 5

_OK_STATUS = 200
_ABSENT_STATUSES = {204, 404, 410}
_BLOCKED_STATUSES = {401, 403}


@dataclass(frozen=True)
class FetcherConfig:
    max_body_bytes: int = 65536
    max_redirects: int = 3

    def __post_init__(self) -> None:
        if self.max_body_bytes < 0:
            raise ValueError(
                f"max_body_bytes must be >= 0; got {self.max_body_bytes}"
            )


_DEFAULT_CONFIG = FetcherConfig()


def fetch_security_txt(
    base_url: str, path: str, config: FetcherConfig | None = None,
) -> FetchOutcome:
    """GET `{base_url}{path}` and map the response to a FetchOutcome.
    Cross-host redirect resolutions land as `inconclusive` so the
    classifier never trusts an off-host security.txt body."""
    config = config or _DEFAULT_CONFIG
    url = urljoin(base_url + "/", path)
    base_origin = origin(base_url)

    with httpx.Client(
        timeout=DEFAULT_TIMEOUT,
        # Spec §Redirect handling: follow same-host redirects up to
        # max_redirects. httpx enforces the count via max_redirects
        # on the client itself; cross-host filtering happens below
        # by comparing the final URL's origin against the base.
        follow_redirects=True,
        max_redirects=config.max_redirects,
        verify=DEFAULT_VERIFY,
    ) as client:
        try:
            response = client.get(
                url,
                headers={
                    "Accept": "text/plain, */*;q=0.1",
                },
            )
        except (httpx.TransportError, httpx.TooManyRedirects):
            # TooManyRedirects is not a TransportError subclass —
            # we explicitly cap at max_redirects=3, so the runtime
            # path is reachable on a real server with a long
            # redirect chain. Spec §Redirect handling treats
            # exceeded-limit as a non-confirming outcome, not a
            # runner crash.
            return FetchOutcome(
                kind="inconclusive", status=None, body="", final_url=url,
            )

    final_url = str(response.url)
    if origin(final_url) != base_origin:
        return FetchOutcome(
            kind="inconclusive", status=response.status_code,
            body="", final_url=final_url,
        )

    body = (response.text or "")[:config.max_body_bytes]
    status = response.status_code

    if status == _OK_STATUS:
        if not body.strip():
            return FetchOutcome(
                kind="absent", status=status, body="", final_url=final_url,
            )
        return FetchOutcome(
            kind="ok", status=status, body=body, final_url=final_url,
        )
    if status in _ABSENT_STATUSES:
        return FetchOutcome(
            kind="absent", status=status, body="", final_url=final_url,
        )
    if status in _BLOCKED_STATUSES:
        return FetchOutcome(
            kind="blocked", status=status, body="", final_url=final_url,
        )
    return FetchOutcome(
        kind="inconclusive", status=status, body="", final_url=final_url,
    )
