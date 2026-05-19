"""Shared URL helpers for stub fetchers/extractors.

`origin(url)` returns `<scheme>://<netloc>` — same-origin filtering
across stubs uses this. Lifted from per-stub copies once we hit
three call sites (frontend_framework fetcher, hidden_routes sitemap
extractor, hidden_routes fetcher in progress).

`classify_same_origin(raw, base_url)` runs the standard
``urljoin → scheme allowlist → same-origin`` triad shared by
source_maps/parser._make_asset and source_maps/resolver.resolve_map_url
(and the deferred frontend_framework refactor in #86). Returns a
typed verdict so each caller can layer its own treatment over the
result (parser collapses bad scheme + cross-origin to None; the
resolver surfaces them as distinct kinds).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urljoin, urlsplit, urlunsplit


def origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


OriginVerdictKind = Literal["ok", "invalid_scheme", "cross_origin"]


@dataclass(frozen=True)
class OriginVerdict:
    """Outcome of the same-origin URL triad. ``absolute_url`` is set
    only when ``kind == "ok"`` so callers can't reach a denied URL
    by accident."""
    kind: OriginVerdictKind
    absolute_url: str | None


def classify_same_origin(raw: str, base_url: str) -> OriginVerdict:
    """Resolve ``raw`` against ``base_url`` and classify the result.

    * ``ok``             — http/https URL same-origin with ``base_url``.
                            ``absolute_url`` populated.
    * ``invalid_scheme`` — scheme not in {http, https}.
    * ``cross_origin``   — http/https URL with a different scheme,
                            host, or port (RFC 6454 origin tuple).
    """
    absolute = urljoin(base_url, raw)
    parts = urlsplit(absolute)
    if parts.scheme not in {"http", "https"}:
        return OriginVerdict(kind="invalid_scheme", absolute_url=None)
    if f"{parts.scheme}://{parts.netloc}" != origin(base_url):
        return OriginVerdict(kind="cross_origin", absolute_url=None)
    return OriginVerdict(kind="ok", absolute_url=absolute)


@dataclass(frozen=True)
class NormalizedUrl:
    """Outcome of resolving a candidate URL against a base URL with
    fragment stripped and query preserved.

    Unlike ``classify_same_origin`` (which drops the URL on
    cross-origin so callers can't reach it by accident), this helper
    keeps the absolute URL on cross-origin so the caller can record
    metadata for off-origin assets (CDN bundles, third-party scripts).
    The ``same_origin`` flag carries the RFC 6454 verdict; it's False
    when ``url`` is None.
    """
    url: str | None
    same_origin: bool


def normalize_url(raw: str, base_url: str) -> NormalizedUrl:
    absolute = urljoin(base_url, raw)
    parts = urlsplit(absolute)
    if parts.scheme not in {"http", "https"}:
        return NormalizedUrl(url=None, same_origin=False)
    url = urlunsplit(
        (parts.scheme, parts.netloc, parts.path, parts.query, ""),
    )
    same = f"{parts.scheme}://{parts.netloc}" == origin(base_url)
    return NormalizedUrl(url=url, same_origin=same)
