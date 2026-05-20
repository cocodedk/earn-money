"""Structured robots.txt parser for stub 1.11.

Turns a raw robots.txt body into a typed `ParsedRobots` with:
- `groups`: tuples of user_agents + (allow|disallow) path hints, per
  spec §Robots groups semantics (a new User-agent after rules starts
  a new group; consecutive User-agents share the same group).
- `sitemaps`: flat tuple of sitemap URLs (global, not per-group).
- `warnings`: malformed and unknown-directive lines, preserved per
  spec §"Unknown directives must be preserved as `unknown_directives`
  but must not fail parsing."

Path-hint filter rules (spec §Path normalization):
- Keep only values that start with `/`.
- Drop full external URLs.
- Preserve wildcards (`*`, `$`) raw — caller decides what to do.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/11-robots-txt.md
"""
from __future__ import annotations

from dataclasses import dataclass


_BOM = "﻿"
_SUPPORTED_DIRECTIVES: frozenset[str] = frozenset({
    "user-agent",
    "allow",
    "disallow",
    "sitemap",
    "crawl-delay",
    "host",
    "clean-param",
})


@dataclass(frozen=True)
class RobotsGroup:
    user_agents: tuple[str, ...]
    allows: tuple[str, ...]
    disallows: tuple[str, ...]


@dataclass(frozen=True)
class ParsedRobots:
    groups: tuple[RobotsGroup, ...]
    sitemaps: tuple[str, ...]
    warnings: tuple[str, ...]


def parse_robots(body: str) -> ParsedRobots:
    """Parse `body` into typed groups + sitemaps + warnings."""
    if not body:
        return ParsedRobots(groups=(), sitemaps=(), warnings=())

    if body.startswith(_BOM):
        body = body[len(_BOM):]

    groups: list[_GroupBuilder] = []
    sitemaps: list[str] = []
    warnings: list[str] = []

    current: _GroupBuilder | None = None
    # `awaiting_rules` flips True after the first User-agent in a
    # group; flips back when a rule (allow/disallow) lands. Next
    # User-agent in `awaiting_rules=False` state starts a NEW group.
    awaiting_rules = False

    for lineno, raw in enumerate(body.splitlines(), start=1):
        line = _strip_comment(raw).strip()
        if not line:
            continue
        if ":" not in line:
            warnings.append(f"line {lineno}: malformed (no colon): {line!r}")
            continue

        name, _, value = line.partition(":")
        directive = name.strip().lower()
        value = value.strip()

        if directive not in _SUPPORTED_DIRECTIVES:
            warnings.append(
                f"line {lineno}: unknown directive {name.strip()!r}"
            )
            continue

        if directive == "user-agent":
            if current is None or not awaiting_rules:
                current = _GroupBuilder()
                groups.append(current)
            current.user_agents.append(value)
            awaiting_rules = True
            continue

        if directive == "sitemap":
            if value:
                sitemaps.append(value)
            continue

        if directive in {"allow", "disallow"}:
            if current is None:
                current = _GroupBuilder()
                groups.append(current)
            awaiting_rules = False
            path = _normalize_path_hint(value)
            if path is None:
                continue
            if directive == "allow":
                current.allows.append(path)
            else:
                current.disallows.append(path)
            continue

        # crawl-delay, host, clean-param: recognised but not
        # consumed by MVP. Keep parsing.
        awaiting_rules = False

    return ParsedRobots(
        groups=tuple(g.freeze() for g in groups),
        sitemaps=tuple(sitemaps),
        warnings=tuple(warnings),
    )


def _strip_comment(raw: str) -> str:
    # Spec §Line parsing rule 4: remove comments beginning with `#`.
    # Inline `#` after the value also starts a comment.
    idx = raw.find("#")
    if idx == -1:
        return raw
    return raw[:idx]


def _normalize_path_hint(value: str) -> str | None:
    """Return the path hint if it's a same-origin-style relative path
    (starts with `/`), else None. External URLs and empty values are
    dropped per spec §Path normalization rules 1-2."""
    if not value:
        return None
    if not value.startswith("/"):
        return None
    return value


@dataclass
class _GroupBuilder:
    user_agents: list[str]
    allows: list[str]
    disallows: list[str]

    def __init__(self) -> None:
        self.user_agents = []
        self.allows = []
        self.disallows = []

    def freeze(self) -> RobotsGroup:
        return RobotsGroup(
            user_agents=tuple(self.user_agents),
            allows=tuple(self.allows),
            disallows=tuple(self.disallows),
        )
