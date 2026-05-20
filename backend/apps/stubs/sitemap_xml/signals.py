"""Pure-function signal detectors for stub 1.12.

Two families per spec §URL classification + §Deterministic indicators:
- `classify_url_scope(loc, base_url)`: returns `in_scope`,
  `out_of_scope`, or `unknown` (when the loc has no scheme and is
  not a relative path). Same-origin = scheme + host + port match
  per RFC 6454.
- `tag_url(loc)`: returns a tuple of deterministic hint tags
  (admin_hint, api_hint, etc.) per the spec's example pattern table.

Tags are deterministic string-pattern labels only. They never
imply a vulnerability — the runner records them as metadata to
seed later-phase checks.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/12-sitemap-xml.md
"""
from __future__ import annotations

from typing import Literal
from urllib.parse import urlsplit

from .._shared.url import origin


Scope = Literal["in_scope", "out_of_scope", "unknown"]


# Spec §Deterministic indicators example pattern table. Each value
# is a tuple of substrings; presence of any one tags the URL. Tags
# stay simple — no regex — to keep the rules auditable and the
# matcher cheap.
_TAG_PATTERNS: dict[str, tuple[str, ...]] = {
    "admin_hint": ("/admin", "/administrator", "/manage", "/console"),
    "api_hint": ("/api/", "/graphql", "/swagger", "/openapi"),
    "auth_hint": ("/login", "/signin", "/signout", "/auth/"),
    "backup_hint": (".bak", ".old", ".zip", ".tar", ".gz"),
    "debug_hint": ("/debug", "/trace", "/actuator", "/phpinfo"),
    "docs_hint": ("/docs", "/documentation", "/wiki"),
    # `/v1/` keeps the trailing slash so `/api/v1.html` doesn't match.
    "legacy_hint": ("/old", "/legacy", "/v1/", "/deprecated"),
    "test_hint": ("/test", "/dev", "/qa"),
    "staging_hint": ("/staging",),
    "upload_hint": ("/upload",),
}


def classify_url_scope(loc: str, base_url: str) -> Scope:
    """Return the URL's scope relative to `base_url`. Relative paths
    (starting with `/`) are treated as in_scope by definition."""
    if not loc:
        return "unknown"
    if loc.startswith("/"):
        return "in_scope"
    if "://" not in loc:
        return "unknown"
    if origin(loc) == origin(base_url):
        return "in_scope"
    return "out_of_scope"


def tag_url(loc: str) -> tuple[str, ...]:
    """Return a tuple of deterministic hint tags for `loc`, in
    pattern-table order. Empty path or no matches → empty tuple."""
    if not loc:
        return ()
    lowered_path = _path_of(loc).lower()
    if not lowered_path:
        return ()
    tags: list[str] = []
    for tag_name, patterns in _TAG_PATTERNS.items():
        if any(p in lowered_path for p in patterns):
            tags.append(tag_name)
    if urlsplit(loc).query:
        tags.append("parameterized_url")
    return tuple(tags)


def _path_of(loc: str) -> str:
    """Extract the path component for matching. Relative path → as-is.
    Absolute URL → urlsplit's path component."""
    if loc.startswith("/"):
        return loc
    return urlsplit(loc).path
