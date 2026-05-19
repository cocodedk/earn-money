"""Pure-function signal detectors for stub 1.11.

Two families:
- `is_sensitive_path(path)`: returns the matched sensitive tokens
  (deduplicated, in path order). Empty tuple means no match.
- `classify_sitemap_origin(sitemap_url, base_url)`: returns
  `"same_origin"` or `"cross_origin"` per RFC 6454 (scheme + host
  + port match).

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/11-robots-txt.md
"""
from __future__ import annotations

import re
from typing import Literal
from urllib.parse import urlsplit


# Per spec §Detection logic "sensitive path matching" — the closed
# token list reproduced from the spec. Matched against path SEGMENTS
# and filename COMPONENTS, never as substring of arbitrary text (so
# `gold` doesn't match `old`).
SENSITIVE_TOKENS: frozenset[str] = frozenset({
    "admin",
    "administrator",
    "backup",
    "backups",
    "bak",
    "old",
    "debug",
    "dev",
    "staging",
    "test",
    "tmp",
    "private",
    "internal",
    "config",
    "configs",
    "secret",
    "secrets",
    "token",
    "tokens",
    "key",
    "keys",
    "db",
    "database",
    "dump",
    "sql",
    "log",
    "logs",
    ".env",
    ".git",
    ".svn",
    ".hg",
})


# Split a path segment on `.`, `-`, `_` to break filenames like
# `db-dump.sql` into {db, dump, sql} for component-level matching.
# The whole segment is also checked (handles `.git`, `.env` which
# would otherwise split into {.git → "", "git"}).
_COMPONENT_SEP = re.compile(r"[.\-_]+")


def is_sensitive_path(path: str) -> tuple[str, ...]:
    """Return the matched sensitive tokens (deduplicated, in first-
    encounter order). Empty tuple = no match.

    Matching is segment- and filename-component based, NOT substring
    — `/products/gold` does not match the `old` token because `gold`
    is not a separate component."""
    if not path:
        return ()
    lowered = path.lower()
    matched: list[str] = []
    seen: set[str] = set()
    for segment in lowered.split("/"):
        if not segment:
            continue
        for component in _segment_components(segment):
            if component in SENSITIVE_TOKENS and component not in seen:
                seen.add(component)
                matched.append(component)
    return tuple(matched)


def _segment_components(segment: str) -> list[str]:
    """Return all matchable components of a path segment in
    deterministic order:
    - The whole segment first (so `.git` and `.env` stay intact and
      the segment-name match wins over its parts).
    - Each `.`/`-`/`_`-separated part, in original left-to-right order
      (so `db-dump.sql` yields [db, dump, sql]).

    Returning a list preserves first-encounter order — a set would
    leak hash randomization into the matched-tokens tuple, breaking
    the docstring's `first-encounter order` promise."""
    components = [segment]
    seen = {segment}
    for part in _COMPONENT_SEP.split(segment):
        if part and part not in seen:
            seen.add(part)
            components.append(part)
    return components


def classify_sitemap_origin(
    sitemap_url: str, base_url: str,
) -> Literal["same_origin", "cross_origin"]:
    """Return `"same_origin"` when `sitemap_url` shares scheme + host
    + port with `base_url`, else `"cross_origin"`. Malformed sitemap
    URLs (no scheme/netloc) are classified `"cross_origin"` — the
    runner must never assume trust without explicit evidence."""
    try:
        sm = urlsplit(sitemap_url)
        base = urlsplit(base_url)
    except ValueError:  # pragma: no cover — urlsplit is permissive
        return "cross_origin"
    if not sm.scheme or not sm.netloc:
        return "cross_origin"
    if sm.scheme != base.scheme:
        return "cross_origin"
    if sm.hostname != base.hostname:
        return "cross_origin"
    if sm.port != base.port:
        return "cross_origin"
    return "same_origin"
