"""Shared URL parameter injection helper for probe tools."""

from __future__ import annotations

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def inject_param(url: str, param: str, value: str) -> str:
    """Return `url` with `param` replaced by `value`, preserving all other params."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params[param] = [value]
    return urlunparse(parsed._replace(query=urlencode({k: v[0] for k, v in params.items()})))
