"""Shared URL helpers for stub fetchers/extractors.

`origin(url)` returns `<scheme>://<netloc>` — same-origin filtering
across stubs uses this. Lifted from per-stub copies once we hit
three call sites (frontend_framework fetcher, hidden_routes sitemap
extractor, hidden_routes fetcher in progress).
"""
from __future__ import annotations

from urllib.parse import urlsplit


def origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"
