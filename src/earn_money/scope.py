"""Parse, validate, write, and hash scope.md files (YAML frontmatter + markdown body)."""

from __future__ import annotations

import hashlib
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(frontmatter.dumps(post).encode("utf-8") + b"\n")


def compute_hash(s: Scope) -> str:
    joined = "\n".join(sorted(s.in_scope)) + "\n--\n" + "\n".join(sorted(s.out_of_scope))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()
