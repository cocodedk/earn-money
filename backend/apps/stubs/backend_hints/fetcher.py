"""Multi-probe fetcher for stub 1.4 backend-hints.

Sends 3 read-only GETs per target: root, /api/, and a forced-404
namespaced path. The 404 probe surfaces framework error pages (Spring
Whitelabel, Werkzeug debugger, Django Disallowed Host etc.) without
probing admin paths the spec explicitly forbids. Per-probe failures
are isolated — one timed-out request does not abort the scan.

Cookies are captured by NAME only; values are sensitive and the spec
requires them never reaching the evidence store. The fetcher returns
`set-cookie` headers' name-portion list per probe, dropping values.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/04-backend-hints.md
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx


DEFAULT_VERIFY = os.environ.get("BACKEND_HINTS_VERIFY", "1") != "0"
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


_PROBE_PATHS: tuple[str, ...] = ("/", "/api/")
_404_PREFIX = "/__scanner_backend_hint_404_"


def fetch_evidence(
    base_url: str, config: FetcherConfig | None = None
) -> dict:
    """Return a bundle: {probes: {<path>: {status, headers, cookies, body}}}.

    Per-probe failures are skipped (no entry for that path) — the
    runner can match against whatever probes did succeed."""
    config = config or _DEFAULT_CONFIG
    probes: dict[str, dict] = {}
    paths = list(_PROBE_PATHS) + [f"{_404_PREFIX}{secrets.token_hex(4)}"]

    with httpx.Client(
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
        verify=DEFAULT_VERIFY,
    ) as client:
        for path in paths:
            url = urljoin(base_url, path)
            probe = _try_probe(client, url, config.max_body_bytes)
            if probe is not None:
                probes[path] = probe

    return {"probes": probes}


def _try_probe(
    client: httpx.Client, url: str, max_body_bytes: int
) -> dict | None:
    try:
        resp = client.get(url)
    except httpx.TransportError:
        return None
    body = (resp.text or "")[:max_body_bytes]
    return {
        "status": resp.status_code,
        # Drop set-cookie from the headers dict — values are sensitive
        # and would leak via header inspection paths. Cookie names are
        # already captured separately under `cookies`.
        "headers": {
            k.lower(): v
            for k, v in resp.headers.items()
            if k.lower() != "set-cookie"
        },
        "cookies": _cookie_names_from_headers(resp.headers),
        "body": body,
    }


def _cookie_names_from_headers(headers: httpx.Headers) -> list[str]:
    """Extract cookie NAMES from Set-Cookie headers. Values are
    deliberately dropped — they're sensitive and we never persist them.

    httpx.Headers supports multiple Set-Cookie entries via .get_list."""
    names: list[str] = []
    for value in headers.get_list("set-cookie"):
        name = value.split("=", 1)[0].strip()
        if name:
            names.append(name)
    return names
