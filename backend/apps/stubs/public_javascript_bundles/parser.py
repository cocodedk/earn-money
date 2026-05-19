"""HTML bundle-candidate extractor for stub 1.15.

Walks an HTML response body and yields ``BundleCandidate`` objects
for the spec's discovery methods (script src, module script src,
modulepreload, preload-as-script, prefetch-when-JS-looking, and
importmap JSON). Pure text parsing — no JavaScript execution and no
network calls; the runner consumes the candidates and decides what
to fetch.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/15-public-javascript-bundles.md
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from .._shared.url import normalize_url


DiscoveryMethod = Literal[
    "script_src", "module_script_src", "modulepreload",
    "preload_script", "prefetch", "importmap",
]
ScriptType = Literal[
    "classic", "module", "importmap", "preload", "prefetch", "unknown",
]


_JS_EXTENSIONS = (".js", ".mjs", ".cjs", ".jsx")

_Raw = tuple[str, DiscoveryMethod, ScriptType]


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
    seen: set[str] = set()
    candidates: list[BundleCandidate] = []
    for raw_url, method, script_type in _walk(soup):
        result = normalize_url(raw_url, base_url)
        if result.url is None or result.url in seen:
            continue
        seen.add(result.url)
        candidates.append(BundleCandidate(
            url=result.url,
            discovery_method=method,
            script_type=script_type,
            same_origin=result.same_origin,
        ))
    return candidates


def _walk(soup: BeautifulSoup):
    for tag in soup.find_all(["script", "link"]):
        if tag.name == "script":
            yield from _from_script(tag)
        else:
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
        return [(src, "module_script_src", "module")]
    return [(src, "script_src", "classic")]


def _from_link(tag) -> _Raw | None:
    rels = {r.lower() for r in (tag.get("rel") or [])}
    href = (tag.get("href") or "").strip()
    if not href:
        return None
    if "modulepreload" in rels:
        return (href, "modulepreload", "module")
    if "preload" in rels:
        if (tag.get("as") or "").lower() == "script":
            return (href, "preload_script", "preload")
        return None
    if "prefetch" in rels:
        if _looks_like_js(href):
            return (href, "prefetch", "prefetch")
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
    return [(url, "importmap", "importmap") for url in urls]


def _looks_like_js(href: str) -> bool:
    """Spec §"Candidate URL extensions and patterns": prefetch entries
    qualify only when the URL strongly indicates JS. Pure extension
    match — content-type belongs to the fetch stage."""
    return urlsplit(href).path.lower().endswith(_JS_EXTENSIONS)
