"""Parsers for stub 1.14 source-maps.

Slice 1 contents:
* ``Asset`` — dataclass for a same-origin JS/CSS asset URL.
* ``parse_html_assets`` — extract candidate JS/CSS assets from a
  page body per spec §"Candidate asset collection".

Subsequent slices add the sourceMappingURL comment extractor
and the Source Map v3 JSON validator alongside this file.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/14-source-maps.md
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .._shared.url import origin


AssetKind = Literal["javascript", "css", "unknown"]

_DEFAULT_MAX_ASSETS = 50


@dataclass(frozen=True)
class Asset:
    """One discovered same-origin JS/CSS asset reference."""
    url: str  # absolute, same-origin with the page base_url
    kind: AssetKind


def parse_html_assets(
    html: str,
    base_url: str,
    max_assets: int = _DEFAULT_MAX_ASSETS,
) -> list[Asset]:
    """Extract candidate JS/CSS asset URLs from ``html``.

    Walks the parsed tree in document order looking at:
    * ``<script src="...">``
    * ``<link rel="stylesheet" href="...">``
    * ``<link rel="preload" as="script" href="...">``
    * ``<link rel="modulepreload" href="...">``

    Same-origin URLs only (compared against ``base_url`` via shared
    ``origin``). Cross-origin, ``data:``, ``javascript:``, ``blob:``
    etc. are dropped silently — those signal a third-party CDN or
    inline asset, not something we should fetch looking for a public
    source map.

    Results are deduplicated by URL while preserving first-seen order
    and capped to ``max_assets``.
    """
    if not html:
        return []
    base_origin = origin(base_url)
    soup = BeautifulSoup(html, "html.parser")

    seen: set[str] = set()
    assets: list[Asset] = []
    for asset in _walk(soup, base_url, base_origin):
        if asset.url in seen:
            continue
        seen.add(asset.url)
        assets.append(asset)
        if len(assets) >= max_assets:
            break
    return assets


def _walk(soup: BeautifulSoup, base_url: str, base_origin: str):
    """Yield candidate assets in document order. Per-tag classification
    lives in the per-element helpers."""
    for tag in soup.find_all(["script", "link"]):
        candidate = _from_tag(tag, base_url, base_origin)
        if candidate is not None:
            yield candidate


def _from_tag(tag, base_url: str, base_origin: str) -> Asset | None:
    if tag.name == "script":
        raw = (tag.get("src") or "").strip()
        return _make_asset(raw, base_url, base_origin, "javascript")
    # BS4 parses `rel` as a list (multi-token HTML attr) or None.
    rels = {r.lower() for r in (tag.get("rel") or [])}
    raw = (tag.get("href") or "").strip()
    if not raw:
        return None
    if "stylesheet" in rels:
        return _make_asset(raw, base_url, base_origin, "css")
    if "modulepreload" in rels:
        return _make_asset(raw, base_url, base_origin, "javascript")
    if "preload" in rels and (tag.get("as") or "").lower() == "script":
        return _make_asset(raw, base_url, base_origin, "javascript")
    return None


def _make_asset(
    raw: str,
    base_url: str,
    base_origin: str,
    kind: AssetKind,
) -> Asset | None:
    if not raw:
        return None
    absolute = urljoin(base_url, raw)
    parts = urlsplit(absolute)
    if parts.scheme not in {"http", "https"}:
        return None
    if origin(absolute) != base_origin:
        return None
    return Asset(url=absolute, kind=kind)
