"""Multi-probe fetcher for stub 1.8 exposed-admin-panels.

Per target:
- GET / (baseline — body becomes part of the soft-404 reference)
- GET /<random-high-entropy-path> + GET /<another-random> (2 soft-404 probes)
- GET each CANDIDATE_PATHS entry

The bundle exposes raw responses keyed by path. Soft-404 comparison +
signal evaluation are the runner's job.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/08-exposed-admin-panels.md
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from .candidates import CANDIDATE_PATHS


DEFAULT_VERIFY = os.environ.get("ADMIN_PANELS_VERIFY", "1") != "0"
DEFAULT_TIMEOUT = 8.0


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
    """Return {baseline, probes} (`probes` keyed by path).

    baseline=None signals "target unreachable" — runner skips. Per-
    probe transport errors are isolated; the loop continues."""
    config = config or _DEFAULT_CONFIG
    nonces = (
        f"/scanner-baseline-{secrets.token_hex(4)}",
        f"/scanner-baseline-{secrets.token_hex(4)}",
    )
    probe_paths = list(nonces) + list(CANDIDATE_PATHS)

    probes: dict[str, dict] = {}
    with httpx.Client(
        timeout=DEFAULT_TIMEOUT,
        # Spec §Request plan default: follow_redirects=False. Redirects
        # carry their own admin-route signal (a 302 to /admin/login is
        # itself evidence) — we want the raw response, not the chase.
        follow_redirects=False,
        verify=DEFAULT_VERIFY,
    ) as client:
        baseline = _try_probe(client, base_url, "/", config.max_body_bytes)
        if baseline is None:
            return {"baseline": None, "probes": {}}
        for path in probe_paths:
            entry = _try_probe(
                client, base_url, path, config.max_body_bytes
            )
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
        "location": resp.headers.get("location"),
    }
