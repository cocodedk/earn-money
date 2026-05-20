"""Scope dataclass + wildcard hostname matcher.

Adapted from `archive/v1/src/earn_money/scope.py` with the v2-pinned
divergence: wildcards do NOT match the bare apex (`*.algolia.net` ≠
`algolia.net`). All other semantics preserved.

Inputs accepted by `matches_scope()` are HOSTNAMES only — no scheme,
no port, no path. URL parsing happens upstream in `scope_check.
enforce_scope()`. Hosts are lower-cased, IDNA-normalised, and
trailing-dot stripped before comparison.

Out-of-scope entries always override in-scope entries ("negative
scope is gospel" per CLAUDE.md hard rules).
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal


Policy = Literal["rate-limited-OK", "manual-only", "ambiguous"]


@dataclass(frozen=True)
class Scope:
    """Parsed `scope.md` frontmatter."""
    platform: str
    slug: str
    policy: Policy
    in_scope: list[str]
    out_of_scope: list[str]
    notes: str = ""
    scope_hash: str = ""
    last_synced: str = ""


def _normalise_host(host: str) -> str:
    """Lower-case, strip one trailing dot, IDNA-encode unicode.

    Rejects host:port, scheme://host, host/path, empty hostnames.
    """
    if not host:
        raise ValueError("empty host")
    if "://" in host:
        raise ValueError(f"malformed host (contains scheme): {host!r}")
    if "/" in host:
        raise ValueError(f"malformed host (contains path): {host!r}")
    if ":" in host:
        raise ValueError(f"malformed host (contains port): {host!r}")
    host = host.lower().rstrip(".")
    if not host:
        raise ValueError("empty host after normalisation")
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError(f"malformed host (IDNA encode failed): {host!r}") from exc


def _matches_any(host: str, patterns: Sequence[str]) -> bool:
    """True if ``host`` matches any pattern. Hosts and patterns are
    already lower-cased; `*.suffix` wildcards match `host.endswith("." + suffix)`
    but NOT the bare apex."""
    for entry in patterns:
        entry_l = entry.lower()
        if entry_l == host:
            return True
        if entry_l.startswith("*."):
            suffix = entry_l[2:]
            if host.endswith("." + suffix):
                return True
    return False


def matches_scope(
    host: str,
    in_scope: Sequence[str],
    out_of_scope: Sequence[str],
) -> bool:
    """True iff ``host`` is in the program's scope.

    Out-of-scope entries always win — a host on the deny-list is never
    in scope, even when a broad wildcard would otherwise admit it.

    Raises ``ValueError`` if ``host`` is malformed (empty / contains
    scheme / path / port / IDNA-unencodable).
    """
    host = _normalise_host(host)
    if _matches_any(host, out_of_scope):
        return False
    return _matches_any(host, in_scope)
