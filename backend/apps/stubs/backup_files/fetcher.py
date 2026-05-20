"""Path-probe fetcher for stub 1.7 backup-files.

Probes the fixed candidate list. Filters out SPA fallthrough (200
HTML for every path) and 404s — surviving responses are real backup
artefacts the runner emits Findings for.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/07-backup-files.md
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from .candidates import CANDIDATES


DEFAULT_VERIFY = os.environ.get("BACKUP_FILES_VERIFY", "1") != "0"
DEFAULT_TIMEOUT = 8.0


_PARSEABLE_STATUS = {200, 203, 206}
_HTML_SHELL_MARKERS = ("<!doctype html", "<html", "<app-root")


@dataclass(frozen=True)
class FetcherConfig:
    max_response_bytes: int = 65536

    def __post_init__(self) -> None:
        if self.max_response_bytes < 0:
            raise ValueError(
                f"max_response_bytes must be >= 0; got {self.max_response_bytes}"
            )


_DEFAULT_CONFIG = FetcherConfig()


def fetch_evidence(
    base_url: str, config: FetcherConfig | None = None
) -> dict:
    config = config or _DEFAULT_CONFIG
    responses: dict[str, dict] = {}
    with httpx.Client(
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
        verify=DEFAULT_VERIFY,
    ) as client:
        for path, source_kind in CANDIDATES:
            url = urljoin(base_url, path)
            entry = _try_probe(client, url, config.max_response_bytes)
            if entry is not None:
                entry["source_kind"] = source_kind
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
    head = body[:200].lower()
    return any(marker in head for marker in _HTML_SHELL_MARKERS)
