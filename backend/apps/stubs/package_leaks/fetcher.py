"""Path-probe fetcher for stub 1.5 package-version-leaks.

Probes a small fixed list of dep-manifest paths. Filters out SPA
fallthrough responses (200 HTML returned for every unknown path —
Juice Shop's Angular SPA is the canonical case) so the JSON/YAML/etc.
parsers never run on HTML bodies. Per-probe transport errors are
isolated.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/05-package-version-leaks.md
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx


DEFAULT_VERIFY = os.environ.get("PACKAGE_LEAKS_VERIFY", "1") != "0"
DEFAULT_TIMEOUT = 5.0


# MVP path set per spec §Direct path probes. Five high-signal manifests
# covering JS/PHP/Python/Ruby/Java; the wider list (yarn.lock, Cargo,
# go.mod, etc.) is deferred to a follow-up.
PROBE_PATHS: tuple[str, ...] = (
    "/package.json",
    "/composer.json",
    "/requirements.txt",
    "/Gemfile",
    "/pom.xml",
)

_PARSEABLE_STATUS = {200, 203, 206}
_HTML_SHELL_MARKERS = ("<!doctype html", "<html", "<app-root")


@dataclass(frozen=True)
class FetcherConfig:
    max_response_bytes: int = 524288

    def __post_init__(self) -> None:
        if self.max_response_bytes < 0:
            raise ValueError(
                f"max_response_bytes must be >= 0; got {self.max_response_bytes}"
            )


_DEFAULT_CONFIG = FetcherConfig()


def fetch_evidence(
    base_url: str, config: FetcherConfig | None = None
) -> dict:
    """Return {responses: {<path>: {status, content_type, body}}}.

    Paths that 404, time out, or return an SPA HTML shell are NOT
    present in the responses map — the runner can iterate the survivors
    without further filtering."""
    config = config or _DEFAULT_CONFIG
    responses: dict[str, dict] = {}

    with httpx.Client(
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
        verify=DEFAULT_VERIFY,
    ) as client:
        for path in PROBE_PATHS:
            url = urljoin(base_url, path)
            entry = _try_probe(client, url, config.max_response_bytes)
            if entry is not None:
                responses[path] = entry

    return {"responses": responses}


def _try_probe(
    client: httpx.Client, url: str, max_bytes: int
) -> dict | None:
    try:
        resp = client.get(url)
    except httpx.TransportError:
        return None
    if resp.status_code not in _PARSEABLE_STATUS:
        return None
    body = (resp.text or "")[:max_bytes]
    if _looks_like_html_shell(body):
        return None
    return {
        "status": resp.status_code,
        "content_type": resp.headers.get("content-type", ""),
        "body": body,
    }


def _looks_like_html_shell(body: str) -> bool:
    """An SPA fallthrough returns 200 + HTML for every unknown path.
    Detect via the conventional doctype/html opening or by an
    Angular-style `<app-root>` marker — these are enough to avoid
    running a JSON parser on the index.html body."""
    head = body[:200].lower()
    return any(marker in head for marker in _HTML_SHELL_MARKERS)
