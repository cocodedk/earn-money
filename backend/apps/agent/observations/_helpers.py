"""Pure data-transform helpers for observation building."""
from __future__ import annotations

from .page import CookieInfo, NetworkEntry


def redact_cookies(raw: list[dict]) -> list[CookieInfo]:
    return [
        CookieInfo(
            name=c.get("name", ""),
            domain=c.get("domain", ""),
            secure=bool(c.get("secure", False)),
            http_only=bool(c.get("httpOnly", False)),
        )
        for c in raw
    ]


def build_network(entries: list[dict]) -> list[NetworkEntry]:
    return [
        NetworkEntry(
            url=e.get("url", ""),
            method=e.get("method", "GET"),
            status=e.get("status", 0),
            content_type=e.get("content_type", ""),
        )
        for e in entries
    ]
