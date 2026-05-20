"""Parsers for stub 1.14 source-maps.

Slice 1 / 2 contents:
* ``Asset`` — dataclass for a same-origin JS/CSS asset URL.
* ``parse_html_assets`` — extract candidate JS/CSS assets from a
  page body per spec §"Candidate asset collection".
* ``extract_source_mapping_url`` — pull the raw ``sourceMappingURL``
  value from a JS or CSS body per spec §"Source map reference
  detection". Does not resolve or validate — slice 3 owns that.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/14-source-maps.md
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from bs4 import BeautifulSoup

from .._shared.url import classify_same_origin


AssetKind = Literal["javascript", "css"]

_DEFAULT_MAX_ASSETS = 50


@dataclass(frozen=True)
class Asset:
    """One discovered same-origin JS/CSS asset reference."""
    url: str
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
    soup = BeautifulSoup(html, "html.parser")

    seen: set[str] = set()
    assets: list[Asset] = []
    for asset in _walk(soup, base_url):
        if asset.url in seen:
            continue
        seen.add(asset.url)
        assets.append(asset)
        if len(assets) >= max_assets:
            break
    return assets


def _walk(soup: BeautifulSoup, base_url: str):
    """Yield candidate assets in document order. Per-tag classification
    lives in the per-element helpers."""
    for tag in soup.find_all(["script", "link"]):
        candidate = _from_tag(tag, base_url)
        if candidate is not None:
            yield candidate


def _from_tag(tag, base_url: str) -> Asset | None:
    if tag.name == "script":
        raw = (tag.get("src") or "").strip()
        if not raw:
            return None
        return _make_asset(raw, base_url, "javascript")
    # BS4 parses `rel` as a list (multi-token HTML attr) or None.
    rels = {r.lower() for r in (tag.get("rel") or [])}
    raw = (tag.get("href") or "").strip()
    if not raw:
        return None
    if "stylesheet" in rels:
        return _make_asset(raw, base_url, "css")
    if "modulepreload" in rels:
        return _make_asset(raw, base_url, "javascript")
    if "preload" in rels and (tag.get("as") or "").lower() == "script":
        return _make_asset(raw, base_url, "javascript")
    return None


def _make_asset(raw: str, base_url: str, kind: AssetKind) -> Asset | None:
    verdict = classify_same_origin(raw, base_url)
    if verdict.kind != "ok" or verdict.absolute_url is None:
        return None
    return Asset(url=verdict.absolute_url, kind=kind)


# Tooling convention: the canonical comment appears at the end of
# the asset body, so when more than one is present, the LAST match
# wins. Earlier matches are usually decoy / debug leftovers.
_JS_SOURCE_MAP_RE = re.compile(
    r"^[ \t]*//[#@][ \t]*sourceMappingURL=[ \t]*(.+?)[ \t]*$",
    re.MULTILINE,
)
_CSS_SOURCE_MAP_RE = re.compile(
    r"/\*#[ \t]*sourceMappingURL=[ \t]*(.+?)[ \t]*\*/",
)


def extract_source_mapping_url(body: str, kind: AssetKind) -> str | None:
    """Pull the raw ``sourceMappingURL`` value from an asset body.

    ``kind="javascript"`` matches both spec JS forms (``//#`` modern
    and ``//@`` legacy). ``kind="css"`` matches the block-comment
    form (``/*# sourceMappingURL=… */``). Cross-form matches are
    rejected: a ``/*# … */`` block inside a JS body and a ``//# …``
    line inside a CSS body both come back as ``None`` so a
    malformed bundler emission can't masquerade as the canonical
    directive.

    Returns the raw value (no URL resolution, no scheme validation).
    """
    if not body:
        return None
    pattern = _JS_SOURCE_MAP_RE if kind == "javascript" else _CSS_SOURCE_MAP_RE
    matches = pattern.findall(body)
    if not matches:
        return None
    return matches[-1].strip()
