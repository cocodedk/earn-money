"""Multi-probe fetcher for stub 1.9 old-endpoints.

Per target:
- GET / (baseline — its body becomes part of the soft-404/fallback
  reference. A homepage-redirect candidate response that resolves to
  the baseline is a generic_fallback, not an endpoint hit.)
- GET /__scanner_control_not_found_<random>
- GET /api/__scanner_control_not_found_<random>
- GET /legacy/__scanner_control_not_found_<random>
  (three nonces spanning root, /api, /legacy so the runner learns the
  per-namespace 404 shape — many apps return different bodies under
  /api than under /.)
- GET each SEEDED_PATHS entry (+ caller-supplied extra_paths).

MVP scope: GET-only (no HEAD-first). The spec recommends HEAD-first as
an optimization but doesn't mandate it for compliance; GET-only keeps
the fetcher simple and aligns with the other Phase-1 stubs. HEAD-first
is a follow-up optimization once request budget pressure justifies it.

The bundle exposes raw responses keyed by path; classification is the
runner's job.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/09-old-endpoints.md
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from .candidates import SEEDED_PATHS


DEFAULT_VERIFY = os.environ.get("OLD_ENDPOINTS_VERIFY", "1") != "0"
DEFAULT_TIMEOUT = 8.0

# Headers the runner needs for classification and signal extraction.
# Capturing only this allowlist keeps cookies, auth tokens, and other
# credential-bearing headers out of the bundle — spec §Safety requires
# they're never persisted, and filtering at fetch time is defense in
# depth against accidental logging of the bundle.
_CAPTURED_HEADERS: frozenset[str] = frozenset({
    "deprecation",
    "sunset",
    "warning",
    "link",
    "location",
})


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
    base_url: str,
    config: FetcherConfig | None = None,
    extra_paths: tuple[str, ...] = (),
) -> dict:
    """Return {baseline, probes} (`probes` keyed by path).

    `extra_paths` lets the runner inject additional same-origin paths
    discovered from earlier phases. MVP wiring passes an empty tuple;
    real `discovered_paths` integration is a follow-up.

    baseline=None signals "target unreachable" — runner skips. Per-
    probe transport errors are isolated; the loop continues."""
    config = config or _DEFAULT_CONFIG
    controls = _control_paths()
    probe_paths = list(controls) + list(SEEDED_PATHS) + list(extra_paths)

    probes: dict[str, dict] = {}
    with httpx.Client(
        timeout=DEFAULT_TIMEOUT,
        # Spec §Request discipline: do not follow redirects. The
        # Location header is itself signal — a homepage redirect on a
        # legacy path classifies as generic_fallback, not endpoint hit.
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


def _control_paths() -> tuple[str, str, str]:
    """Three randomised control paths spanning root, /api, and /legacy.
    Per-namespace coverage so the runner can detect e.g. an SPA shell
    that only fires under /, distinct from a JSON 404 under /api."""
    nonce = secrets.token_hex(6)
    return (
        f"/__scanner_control_not_found_{nonce}",
        f"/api/__scanner_control_not_found_{nonce}",
        f"/legacy/__scanner_control_not_found_{nonce}",
    )


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
        "headers": _capture_headers(resp.headers),
        "url": str(resp.url),
        "location": resp.headers.get("location"),
    }


def _capture_headers(headers: httpx.Headers) -> dict[str, str]:
    """Return only allowlisted headers, combining multi-values with
    `,` per RFC 7230 §3.2.2 so RFC 8288 multi-Link headers don't lose
    a `rel="deprecation"` to dict-collapse."""
    out: dict[str, list[str]] = {}
    for raw_key, value in headers.multi_items():
        key = raw_key.lower()
        if key not in _CAPTURED_HEADERS:
            continue
        out.setdefault(key, []).append(value)
    return {key: ", ".join(values) for key, values in out.items()}
