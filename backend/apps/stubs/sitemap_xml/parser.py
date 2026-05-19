"""Tolerant XML sitemap parser for stub 1.12.

Spec §URL extraction: extract `<url><loc>` for urlset sitemaps and
`<sitemap><loc>` for sitemap indexes, with optional lastmod /
changefreq / priority on urlset entries.

Regex-based — `xml.etree.ElementTree` rejects unclosed tags and
common real-world sitemap quirks (Shopify/Google output frequently
trips it). The regex approach mirrors stub 1.6's existing extractor;
this slice adds the structured-entry shape (per-URL meta + kind
classification) the spec calls for.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/12-sitemap-xml.md
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urldefrag


SitemapKind = Literal["urlset", "sitemapindex", "unknown"]


@dataclass(frozen=True)
class SitemapEntry:
    """One `<url>` or `<sitemap>` block. `loc` is required; the meta
    fields are optional and only populated when found."""
    loc: str
    lastmod: str | None = None
    changefreq: str | None = None
    priority: str | None = None


@dataclass(frozen=True)
class ParsedSitemap:
    kind: SitemapKind
    entries: tuple[SitemapEntry, ...]


_URLSET_RE = re.compile(r"<urlset\b", re.IGNORECASE)
_SITEMAPINDEX_RE = re.compile(r"<sitemapindex\b", re.IGNORECASE)
_URL_BLOCK_RE = re.compile(
    r"<url\b[^>]*>(.*?)</url\s*>", re.IGNORECASE | re.DOTALL,
)
_SITEMAP_BLOCK_RE = re.compile(
    r"<sitemap\b[^>]*>(.*?)</sitemap\s*>", re.IGNORECASE | re.DOTALL,
)
_LOC_RE = re.compile(
    r"<loc\b[^>]*>\s*(.+?)\s*</loc\s*>", re.IGNORECASE | re.DOTALL,
)
_LASTMOD_RE = re.compile(
    r"<lastmod\b[^>]*>\s*(.+?)\s*</lastmod\s*>", re.IGNORECASE | re.DOTALL,
)
_CHANGEFREQ_RE = re.compile(
    r"<changefreq\b[^>]*>\s*(.+?)\s*</changefreq\s*>",
    re.IGNORECASE | re.DOTALL,
)
_PRIORITY_RE = re.compile(
    r"<priority\b[^>]*>\s*(.+?)\s*</priority\s*>",
    re.IGNORECASE | re.DOTALL,
)
_CDATA_RE = re.compile(r"^<!\[CDATA\[(.*?)\]\]>$", re.DOTALL)


def parse_sitemap_xml(body: str) -> ParsedSitemap:
    """Return a ParsedSitemap describing the body. `kind="unknown"`
    means the body doesn't look like an XML sitemap at all (HTML,
    empty, or unidentified structure)."""
    if not body:
        return ParsedSitemap(kind="unknown", entries=())

    if _SITEMAPINDEX_RE.search(body):
        kind: SitemapKind = "sitemapindex"
        block_re = _SITEMAP_BLOCK_RE
    elif _URLSET_RE.search(body):
        kind = "urlset"
        block_re = _URL_BLOCK_RE
    else:
        return ParsedSitemap(kind="unknown", entries=())

    seen_locs: set[str] = set()
    entries: list[SitemapEntry] = []
    for match in block_re.finditer(body):
        entry = _extract_entry(match.group(1), include_meta=(kind == "urlset"))
        if entry is None or entry.loc in seen_locs:
            continue
        seen_locs.add(entry.loc)
        entries.append(entry)

    return ParsedSitemap(kind=kind, entries=tuple(entries))


def _extract_entry(
    block: str, *, include_meta: bool,
) -> SitemapEntry | None:
    loc_match = _LOC_RE.search(block)
    if loc_match is None:
        return None
    loc = _strip_cdata(loc_match.group(1).strip())
    # Spec §URL normalization: remove fragments.
    loc, _ = urldefrag(loc)
    if not loc:
        return None

    lastmod_match = _LASTMOD_RE.search(block)
    lastmod = lastmod_match.group(1).strip() if lastmod_match else None
    if not include_meta:
        # sitemapindex entries carry only loc + lastmod per spec.
        return SitemapEntry(loc=loc, lastmod=lastmod)

    changefreq_match = _CHANGEFREQ_RE.search(block)
    priority_match = _PRIORITY_RE.search(block)
    return SitemapEntry(
        loc=loc,
        lastmod=lastmod,
        changefreq=(
            changefreq_match.group(1).strip()
            if changefreq_match else None
        ),
        priority=(
            priority_match.group(1).strip() if priority_match else None
        ),
    )


def _strip_cdata(value: str) -> str:
    m = _CDATA_RE.match(value)
    return m.group(1).strip() if m else value
