"""sitemap.xml path extractor for stub 1.6.

Tolerant regex-based extraction (not strict XML parsing) — real-world
sitemaps frequently emit slightly invalid XML, and we'd rather get
the URLs than fail on an unclosed tag. Same-origin filter strips
cross-origin entries (sitemaps occasionally include CDN URLs the
runner shouldn't follow back into another scope).
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from ..._shared.url import origin


# Real-world sitemaps from Google/Shopify/several CMS plugins wrap
# URLs as <loc><![CDATA[https://...]]></loc>. The inner regex captures
# CDATA-wrapped or plain forms; the post-match strip removes the
# wrapper if present.
_LOC_RE = re.compile(r"<loc>\s*(.+?)\s*</loc>", re.IGNORECASE | re.DOTALL)
_CDATA_RE = re.compile(r"^<!\[CDATA\[(.*?)\]\]>$", re.DOTALL)

# Defence-in-depth: extractors must not be at the mercy of the
# fetcher's body cap. Cap input size locally so a 10MB sitemap can't
# pin memory inside the regex engine.
_MAX_BODY_BYTES = 1_048_576  # 1 MiB


def parse_sitemap_xml(body: str, base_url: str) -> list[str]:
    body = body[:_MAX_BODY_BYTES]
    if not body or "<loc" not in body.lower():
        return []
    base_origin = origin(base_url)
    out: list[str] = []
    seen: set[str] = set()
    for match in _LOC_RE.finditer(body):
        url = _strip_cdata(match.group(1).strip())
        path = _to_same_origin_path(url, base_origin)
        if path is None or path in seen:
            continue
        seen.add(path)
        out.append(path)
    return out


def _strip_cdata(value: str) -> str:
    m = _CDATA_RE.match(value)
    return m.group(1).strip() if m else value


def _to_same_origin_path(url: str, base_origin: str) -> str | None:
    """Return the path component if `url` is same-origin (or already a
    relative path); None for cross-origin or unparseable URLs."""
    if "://" not in url:
        return url if url.startswith("/") else None
    if origin(url) != base_origin:
        return None
    return urlsplit(url).path or "/"
