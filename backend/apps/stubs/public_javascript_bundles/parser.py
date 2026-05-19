"""HTML bundle-candidate extractor for stub 1.15.

Walks an HTML response body looking for JavaScript bundle references
across the spec's discovery methods (script src, module script src,
modulepreload, preload-as-script, prefetch when JS-looking, and
importmap JSON). Each result is a BundleCandidate with the
normalized absolute URL, the discovery method, the script type, and
whether the URL is same-origin with the page.

Pure text parsing — no JavaScript execution, no network calls.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/15-public-javascript-bundles.md
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from .._shared.url import origin


DiscoveryMethod = Literal[
    "script_src", "module_script_src", "modulepreload",
    "preload_script", "prefetch", "importmap",
]
ScriptType = Literal[
    "classic", "module", "importmap", "preload", "prefetch", "unknown",
]


_JS_EXTENSIONS = (".js", ".mjs", ".cjs", ".jsx")


@dataclass(frozen=True)
class BundleCandidate:
    url: str
    discovery_method: DiscoveryMethod
    script_type: ScriptType
    same_origin: bool


def extract_bundle_candidates(
    html: str, base_url: str,
) -> list[BundleCandidate]:
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    base_origin = origin(base_url)
    seen: set[str] = set()
    candidates: list[BundleCandidate] = []
    for raw in _walk(soup):
        url = _normalize(raw.url, base_url)
        if url is None or url in seen:
            continue
        seen.add(url)
        candidates.append(BundleCandidate(
            url=url,
            discovery_method=raw.method,
            script_type=raw.script_type,
            same_origin=(origin(url) == base_origin),
        ))
    return candidates


@dataclass(frozen=True)
class _Raw:
    url: str
    method: DiscoveryMethod
    script_type: ScriptType


def _walk(soup: BeautifulSoup):
    for tag in soup.find_all("script"):
        yield from _from_script(tag)
    for tag in soup.find_all("link"):
        single = _from_link(tag)
        if single is not None:
            yield single


def _from_script(tag) -> list[_Raw]:
    script_type = (tag.get("type") or "").lower()
    if script_type == "importmap":
        return _from_importmap(tag.string or "")
    src = (tag.get("src") or "").strip()
    if not src:
        return []
    if script_type == "module":
        return [_Raw(src, "module_script_src", "module")]
    return [_Raw(src, "script_src", "classic")]


def _from_link(tag) -> _Raw | None:
    rels = {r.lower() for r in (tag.get("rel") or [])}
    href = (tag.get("href") or "").strip()
    if not href:
        return None
    if "modulepreload" in rels:
        return _Raw(href, "modulepreload", "module")
    if "preload" in rels:
        if (tag.get("as") or "").lower() == "script":
            return _Raw(href, "preload_script", "preload")
        return None
    if "prefetch" in rels:
        if _looks_like_js(href):
            return _Raw(href, "prefetch", "prefetch")
        return None
    return None


def _from_importmap(body: str) -> list[_Raw]:
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(data, dict):
        return []
    urls: list[str] = []
    imports = data.get("imports")
    if isinstance(imports, dict):
        urls.extend(v for v in imports.values() if isinstance(v, str))
    scopes = data.get("scopes")
    if isinstance(scopes, dict):
        for entries in scopes.values():
            if isinstance(entries, dict):
                urls.extend(v for v in entries.values() if isinstance(v, str))
    return [_Raw(url, "importmap", "importmap") for url in urls]


def _looks_like_js(href: str) -> bool:
    """Spec §"Candidate URL extensions and patterns": prefetch entries
    only count when the URL strongly indicates JavaScript. Pure
    extension match — content-type belongs to the fetch stage."""
    path = urlsplit(href).path.lower()
    return any(path.endswith(ext) for ext in _JS_EXTENSIONS)


def _normalize(raw: str, base_url: str) -> str | None:
    """Resolve relative against base_url, strip fragment, keep query.
    Returns None for unsupported schemes (data:, javascript:, blob:,
    mailto: …)."""
    absolute = urljoin(base_url, raw)
    parts = urlsplit(absolute)
    if parts.scheme not in {"http", "https"}:
        return None
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, parts.query, ""),
    )
