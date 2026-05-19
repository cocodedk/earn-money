"""HTTP fetcher for stub 1.15 public-javascript-bundles.

`fetch_bundle(url, config)` performs a single GET and returns a
`BundleFetchOutcome`. Classification follows spec §"Fetch bundle
metadata":

* 200 with a JavaScript content type → ``ok``
* 200 with HTML / JSON / image / CSS / font / XML → ``non_js``
* 200 with missing or generic content type → ``ok`` only when the
  URL path strongly indicates JavaScript AND the body starts like
  JavaScript (keeps the runner from minting confirmed-JS findings
  on arbitrary octet-stream payloads)
* 404 / 410 → ``absent``
* 401 / 403 → ``blocked``
* transport / TLS / DNS errors, too-many-redirects, unexpected
  status → ``inconclusive``

Body is capped at ``max_body_bytes`` and ``truncated`` is set when
the source body would have exceeded the cap. The sha256 is computed
over the bytes actually read, so a truncated bundle hashes to its
truncated content (matches spec §"Persistence" `sha256` semantics).

No same-origin check at this layer — the parser (slice 1) flags
cross-origin candidates and the runner decides whether to fetch
them; the fetcher is a thin HTTP wrapper.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/15-public-javascript-bundles.md
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

import httpx

from .._shared.hashing import body_hash_bytes


DEFAULT_VERIFY = os.environ.get("PUBLIC_JS_BUNDLES_VERIFY", "1") != "0"

_ABSENT_STATUSES = {404, 410}
_BLOCKED_STATUSES = {401, 403}

_JS_CONTENT_TYPES = frozenset({
    "application/javascript",
    "text/javascript",
    "application/x-javascript",
    "text/ecmascript",
    "application/ecmascript",
})

_JS_URL_EXTENSIONS = (".js", ".mjs", ".cjs", ".jsx")

_GENERIC_CONTENT_TYPES = frozenset({"", "application/octet-stream", "text/plain"})

# Prefix patterns that signal JavaScript on a generic content type.
# Spec: "body starts like JavaScript" — strict prefix match (post-
# leading-whitespace), no substring fallback. The heuristic only
# kicks in when the URL also looks like JS, so the false-positive
# surface is bounded.
_JS_BODY_MARKERS = (
    "//", "/*", "function", "var ", "const ", "let ",
    "import ", "export ", "(function", "!function",
)

_JS_BODY_PROBE_BYTES = 1024


BundleFetchKind = Literal["ok", "non_js", "absent", "blocked", "inconclusive"]


@dataclass(frozen=True)
class BundleFetcherConfig:
    """Per-call knobs. Defaults match spec §Inputs."""
    max_body_bytes: int = 5_242_880  # 5 MiB
    max_redirects: int = 3
    timeout_seconds: float = 10.0


@dataclass(frozen=True)
class BundleFetchOutcome:
    kind: BundleFetchKind
    status: int | None
    body: str
    final_url: str
    content_type: str
    content_length: int | None
    bytes_read: int
    truncated: bool
    sha256: str | None
    etag: str | None
    last_modified: str | None
    cache_control: str | None


_DEFAULT_CONFIG = BundleFetcherConfig()


def fetch_bundle(
    url: str, config: BundleFetcherConfig | None = None,
) -> BundleFetchOutcome:
    config = config or _DEFAULT_CONFIG
    with httpx.Client(
        timeout=config.timeout_seconds,
        follow_redirects=True,
        max_redirects=config.max_redirects,
        verify=DEFAULT_VERIFY,
    ) as client:
        try:
            response = client.get(url)
        except (httpx.TransportError, httpx.TooManyRedirects):
            return _transport_failure(url)
    return _classify(response, config.max_body_bytes)


def _transport_failure(url: str) -> BundleFetchOutcome:
    return BundleFetchOutcome(
        kind="inconclusive", status=None, body="", final_url=url,
        content_type="", content_length=None, bytes_read=0,
        truncated=False, sha256=None, etag=None,
        last_modified=None, cache_control=None,
    )


def _classify(
    response: httpx.Response, max_body_bytes: int,
) -> BundleFetchOutcome:
    final_url = str(response.url)
    raw_ct = response.headers.get("content-type", "")
    content_type = raw_ct.split(";", 1)[0].strip().lower()
    # Cap and hash in WIRE BYTES per spec §"Fetch bundle metadata":
    # max_bundle_bytes is a byte budget, the sha256 is over the bytes
    # read. Slicing response.text (a decoded str) would either let a
    # multibyte-UTF-8 payload past the budget or undercount it.
    raw_bytes = response.content or b""
    body_bytes = raw_bytes[:max_body_bytes]
    truncated = len(raw_bytes) > max_body_bytes
    body = body_bytes.decode("utf-8", errors="replace")
    bytes_read = len(body_bytes)
    status = response.status_code

    kind = _kind_for(status, content_type, final_url, body)
    if kind in {"ok", "non_js", "blocked"}:
        sha256 = body_hash_bytes(body_bytes)
    else:
        # absent / inconclusive responses don't carry meaningful
        # bundle bytes; drop the body to keep evidence focused.
        body, bytes_read, truncated, sha256 = "", 0, False, None

    return BundleFetchOutcome(
        kind=kind, status=status, body=body, final_url=final_url,
        content_type=content_type,
        content_length=_parse_content_length(response.headers),
        bytes_read=bytes_read, truncated=truncated, sha256=sha256,
        etag=response.headers.get("etag"),
        last_modified=response.headers.get("last-modified"),
        cache_control=response.headers.get("cache-control"),
    )


def _kind_for(
    status: int, content_type: str, final_url: str, body: str,
) -> BundleFetchKind:
    if status in _ABSENT_STATUSES:
        return "absent"
    if status in _BLOCKED_STATUSES:
        return "blocked"
    if status != 200:
        return "inconclusive"
    if content_type in _JS_CONTENT_TYPES:
        return "ok"
    if content_type in _GENERIC_CONTENT_TYPES:
        if _url_looks_like_js(final_url) and _body_looks_like_js(body):
            return "ok"
    return "non_js"


def _url_looks_like_js(url: str) -> bool:
    return urlsplit(url).path.lower().endswith(_JS_URL_EXTENSIONS)


def _body_looks_like_js(body: str) -> bool:
    head = body[:_JS_BODY_PROBE_BYTES].lstrip()
    if not head:
        return False
    return any(head.startswith(marker) for marker in _JS_BODY_MARKERS)


def _parse_content_length(headers) -> int | None:
    raw = headers.get("content-length")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None
