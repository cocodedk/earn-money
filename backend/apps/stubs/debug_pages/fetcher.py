"""Multi-probe fetcher for stub 1.10 debug-pages.

Per target:
- GET / (baseline — its body becomes the soft-404/fallback reference.
  A response whose body equals the baseline is a generic_fallback,
  not a real debug page.)
- GET each SEEDED_PATHS entry from candidates.py.

MVP scope: GET-only. The spec's HEAD-first optimization (§Request
discipline step 1) is a follow-up; the seeded path list is small
enough that the GET cost is bounded.

Bodies are truncated to `max_body_bytes` per spec §"max_response_bytes
default 256000" — the runner marks the evidence as truncated upstream
when truncation actually fires.

Headers are filtered to CAPTURED_HEADERS at fetch time so cookies,
authorization tokens, and other credential-bearing headers never
reach the in-memory bundle (defense in depth against accidental
logging of the bundle by downstream code).

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/10-debug-pages.md
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from .candidates import CAPTURED_HEADERS, SEEDED_PATHS


DEFAULT_VERIFY = os.environ.get("DEBUG_PAGES_VERIFY", "1") != "0"
DEFAULT_TIMEOUT = 8.0

# Reserved path-segment marker shared with the runner. Stub 1.10
# doesn't currently emit control nonces (the seeded debug paths are
# already framework-specific enough that a generic baseline-body
# filter does the soft-404 work), but the constant exists so the
# runner's CONTROL_MARKER-in-path skip logic stays uniform across
# stubs.
CONTROL_MARKER = "__scanner_control_"

_CAPTURED_HEADERS_FROZEN: frozenset[str] = frozenset(CAPTURED_HEADERS)


@dataclass(frozen=True)
class FetcherConfig:
    # Spec default: 256000. Override to a lower cap in tests so a
    # synthetic long body's truncation is visible.
    max_body_bytes: int = 256000

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

    `extra_paths` lets the runner inject same-origin paths discovered
    by earlier phases (robots, sitemap, JS routes). MVP wiring passes
    an empty tuple; real discovered_paths integration is a follow-up.

    baseline=None signals "target unreachable" — runner skips. Per-
    probe transport errors are isolated; the loop continues."""
    config = config or _DEFAULT_CONFIG
    probe_paths = list(SEEDED_PATHS) + list(extra_paths)

    probes: dict[str, dict] = {}
    with httpx.Client(
        timeout=DEFAULT_TIMEOUT,
        # Spec §Redirect handling: classify the Location header
        # ourselves rather than chasing 3xx automatically — an
        # off-origin redirect to attacker-controlled host must not
        # result in the scanner fetching from that host.
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
    client: httpx.Client, base_url: str, path: str, max_body_bytes: int,
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
    """Return only allowlisted headers, lowercased and combined per
    RFC 7230 §3.2.2 multi-value comma join."""
    out: dict[str, list[str]] = {}
    for raw_key, value in headers.multi_items():
        key = raw_key.lower()
        if key not in _CAPTURED_HEADERS_FROZEN:
            continue
        out.setdefault(key, []).append(value)
    return {key: ", ".join(values) for key, values in out.items()}
