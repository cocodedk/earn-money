"""Safe writer for agent-proposed scripts + tool-gap notes.

Anything the agent proposes lands under `scratch/agent-proposals/` with
the executable bit OFF and a `.proposal` extension on the filename so
no cron or human muscle-memory can run it accidentally. Operator
reviews, renames, chmods, and runs by hand.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

# Filename whitelist: kebab/snake/alphanum, max 60 chars, single dot for ext.
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,59}$")
_ALLOWED_LANGS: frozenset[str] = frozenset({"sh", "py"})


class InvalidProposal(Exception):
    """Raised when an agent proposal fails the safety filter."""


def _now_slug() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def _validate_slug(value: str) -> str:
    if not _SLUG_RE.match(value):
        raise InvalidProposal(
            f"slug must match [a-z0-9][a-z0-9_-]{{0,59}}, got {value!r}"
        )
    return value


def write_script_proposal(
    proposals_root: Path,
    *,
    slug: str,
    language: str,
    body: str,
    rationale: str,
) -> Path:
    """Persist an agent-proposed one-off script. Returns the written path.

    The file is created without the executable bit. Operator must
    explicitly review + `chmod +x` before running.
    """
    if language not in _ALLOWED_LANGS:
        raise InvalidProposal(
            f"language must be one of {sorted(_ALLOWED_LANGS)}, got {language!r}"
        )
    slug = _validate_slug(slug)
    target_dir = proposals_root / "scripts"
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{_now_slug()}-{slug}.proposal.{language}"
    target = target_dir / filename
    header = _script_header(language, rationale)
    target.write_text(header + body, encoding="utf-8")
    return target


def write_tool_gap_proposal(
    proposals_root: Path,
    *,
    slug: str,
    rationale: str,
    design_md: str,
) -> Path:
    """Persist an agent-proposed new-tool note. Returns the written path."""
    slug = _validate_slug(slug)
    target_dir = proposals_root / "tool-gaps"
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{_now_slug()}-{slug}.proposal.md"
    target = target_dir / filename
    target.write_text(
        f"# Tool-gap proposal — {slug}\n\n"
        f"_Agent-proposed at {datetime.now(UTC).isoformat()}_\n\n"
        f"## Rationale\n{rationale}\n\n"
        f"## Design sketch\n{design_md}\n",
        encoding="utf-8",
    )
    return target


def _script_header(language: str, rationale: str) -> str:
    when = datetime.now(UTC).isoformat()
    if language == "sh":
        return (
            "#!/bin/sh\n"
            "# AGENT PROPOSAL — REVIEW BEFORE EXECUTING.\n"
            f"# Generated: {when}\n"
            f"# Rationale: {rationale}\n"
            "# Executable bit is OFF on purpose. `chmod +x` after review.\n"
            "set -eu\n\n"
        )
    return (
        '"""AGENT PROPOSAL — REVIEW BEFORE EXECUTING.\n'
        f"Generated: {when}\n"
        f"Rationale: {rationale}\n"
        "Executable bit is OFF on purpose. `chmod +x` after review.\n"
        '"""\n\n'
    )
