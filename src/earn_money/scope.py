"""Parse, validate, write, and hash scope.md files (YAML frontmatter + markdown body)."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import frontmatter

Policy = Literal["rate-limited-OK", "manual-only", "ambiguous"]
_ALLOWED_POLICIES: frozenset[str] = frozenset({"rate-limited-OK", "manual-only", "ambiguous"})


class InvalidScope(Exception):
    """Raised when scope.md is malformed or has an unrecognised policy."""


@dataclass(frozen=True)
class Scope:
    platform: str
    slug: str
    policy: Policy
    in_scope: list[str]
    out_of_scope: list[str]
    notes: str
    scope_hash: str
    last_synced: str


def read_scope(path: Path) -> Scope:
    post = frontmatter.load(path)
    meta = post.metadata
    policy = meta.get("policy", "")
    if policy not in _ALLOWED_POLICIES:
        raise InvalidScope(
            f"{path}: unknown policy {policy!r}. "
            f"Allowed: {sorted(_ALLOWED_POLICIES)}"
        )
    return Scope(
        platform=str(meta["platform"]),
        slug=str(meta["slug"]),
        policy=policy,
        in_scope=list(meta.get("in_scope") or []),
        out_of_scope=list(meta.get("out_of_scope") or []),
        notes=post.content,
        scope_hash=str(meta.get("scope_hash") or ""),
        last_synced=str(meta.get("last_synced") or ""),
    )


def write_scope(path: Path, s: Scope) -> None:
    post = frontmatter.Post(
        content=s.notes,
        platform=s.platform,
        slug=s.slug,
        policy=s.policy,
        scope_hash=s.scope_hash,
        last_synced=s.last_synced,
        in_scope=list(s.in_scope),
        out_of_scope=list(s.out_of_scope),
    )
    serialized = frontmatter.dumps(post)
    if not serialized.endswith("\n"):
        serialized += "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialized, encoding="utf-8")


def compute_hash(s: Scope) -> str:
    joined = "\n".join(sorted(s.in_scope)) + "\n--\n" + "\n".join(sorted(s.out_of_scope))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _matches_any(fqdn: str, patterns: Sequence[str]) -> bool:
    """True if ``fqdn`` matches any pattern. Patterns are either literal
    hostnames or ``*.suffix`` wildcards that match the suffix itself plus
    every descendant."""
    fqdn = fqdn.lower()
    for entry in patterns:
        entry_l = entry.lower()
        if entry_l == fqdn:
            return True
        if entry_l.startswith("*."):
            suffix = entry_l[2:]
            if fqdn.endswith("." + suffix) or fqdn == suffix:
                return True
    return False


def is_in_scope(
    fqdn: str, in_scope: Sequence[str], out_of_scope: Sequence[str] = ()
) -> bool:
    # Negative scope is gospel — a host on the deny-list is never in scope,
    # even when a broad wildcard would otherwise admit it.
    if _matches_any(fqdn, out_of_scope):
        return False
    return _matches_any(fqdn, in_scope)


def explicit_literals(in_scope: Sequence[str]) -> frozenset[str]:
    """Lowercased frozenset of the literal (non-wildcard) entries in
    ``in_scope``.

    Precomputed once per scope so sampling code can decide
    "is this fqdn program-authored vs wildcard-resolved?" with an O(1)
    set lookup rather than re-scanning the in_scope list per asset.
    The explicit ones (`www.algolia.com`, `dashboard.algolia.com`) are
    usually the operator-facing assets — a far better sample for
    `--max-targets` than the alphabetical-first wildcard fan-out
    (`c3-eu-1.algolia.net` matched via `*.algolia.net`)."""
    return frozenset(e.lower() for e in in_scope if not e.startswith("*."))
