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


_LOC_RE = re.compile(r"<loc>\s*([^<]+?)\s*</loc>", re.IGNORECASE | re.DOTALL)


def parse_sitemap_xml(body: str, base_url: str) -> list[str]:
    if not body or "<loc" not in body.lower():
        return []
    base_origin = _origin(base_url)
    out: list[str] = []
    seen: set[str] = set()
    for match in _LOC_RE.finditer(body):
        url = match.group(1).strip()
        path = _to_same_origin_path(url, base_origin)
        if path is None or path in seen:
            continue
        seen.add(path)
        out.append(path)
    return out


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def _to_same_origin_path(url: str, base_origin: str) -> str | None:
    """Return the path component if `url` is same-origin (or already a
    relative path); None for cross-origin or unparseable URLs."""
    if "://" not in url:
        return url if url.startswith("/") else None
    if _origin(url) != base_origin:
        return None
    return urlsplit(url).path or "/"
