"""Multi-probe fetcher for stub 1.6 hidden-routes.

Per target:
- GET / (baseline — body becomes part of the soft-404 reference)
- GET /.well-known/scanner-nonexistent-<nonce> and
  GET /scanner-nonexistent-<nonce> (the two soft-404 probes)
- GET /robots.txt, /sitemap.xml (metadata files for passive extraction)
- GET each path in COMMON_PATHS (~8 high-signal admin/api/docs probes)

The bundle exposes raw responses. Soft-404 comparison + dedup is the
runner's job; the fetcher just gathers.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/06-hidden-routes.md
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx


DEFAULT_VERIFY = os.environ.get("HIDDEN_ROUTES_VERIFY", "1") != "0"
DEFAULT_TIMEOUT = 8.0


# Conservative built-in list per spec §Add small common-path probes.
# Eight high-signal entries — much smaller than the spec's full list
# to honour the rate-limited+passive defaults during the MVP.
COMMON_PATHS: tuple[str, ...] = (
    "/admin",
    "/login",
    "/api",
    "/api/v1",
    "/graphql",
    "/swagger",
    "/actuator",
    "/docs",
)

_METADATA_PATHS: tuple[str, ...] = ("/robots.txt", "/sitemap.xml")


@dataclass(frozen=True)
class FetcherConfig:
    max_body_bytes: int = 65536

    def __post_init__(self) -> None:
        if self.max_body_bytes < 0:
            raise ValueError(
                f"max_body_bytes must be >= 0; got {self.max_body_bytes}"
            )


_DEFAULT_CONFIG = FetcherConfig()


def fetch_evidence(
    base_url: str, config: FetcherConfig | None = None
) -> dict:
    """Return {baseline, probes}.

    baseline: dict with {status, body, url} for /, or None if the
    baseline GET failed (signals "target unreachable" — runner skips).
    probes: dict[path → {status, body}] across nonce + metadata +
    common-path probes that didn't TransportError. The runner builds
    the soft-404 profile from the two nonce probes and compares the
    remaining probes against it."""
    config = config or _DEFAULT_CONFIG
    nonces = (
        f"/.well-known/scanner_nonexistent_{secrets.token_hex(4)}",
        f"/scanner_nonexistent_{secrets.token_hex(4)}",
    )
    probe_paths = (
        list(nonces) + list(_METADATA_PATHS) + list(COMMON_PATHS)
    )

    probes: dict[str, dict] = {}
    with httpx.Client(
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
        verify=DEFAULT_VERIFY,
    ) as client:
        baseline = _try_probe(client, base_url, "/", config.max_body_bytes)
        if baseline is None:
            return {"baseline": None, "probes": {}}
        for path in probe_paths:
            entry = _try_probe(client, base_url, path, config.max_body_bytes)
            if entry is not None:
                probes[path] = entry

    return {"baseline": baseline, "probes": probes}


def _try_probe(
    client: httpx.Client, base_url: str, path: str, max_body_bytes: int
) -> dict | None:
    url = urljoin(base_url, path)
    try:
        resp = client.get(url)
    except httpx.TransportError:
        return None
    return {
        "status": resp.status_code,
        "body": (resp.text or "")[:max_body_bytes],
        "url": str(resp.url),
    }
